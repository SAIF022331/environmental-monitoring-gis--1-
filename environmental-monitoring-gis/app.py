import os
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, abort
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import func, desc, text
from geoalchemy2.elements import WKTElement
from config import Config
from app_extensions import db

login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config: app.config.update(test_config)
    db.init_app(app); login_manager.init_app(app); login_manager.login_view = "login"
    csrf.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": []}}, supports_credentials=False)
    from models import User, MonitoringStation, EnvironmentalObservation
    @login_manager.user_loader
    def load_user(user_id): return db.session.get(User, int(user_id))

    def admin_required(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role != "Admin": return jsonify({"error":"Administrator role required"}), 403
            return fn(*args, **kwargs)
        return wrapped
    def editor_required(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in ("Admin",): return jsonify({"error":"Admin role required to modify records"}), 403
            return fn(*args, **kwargs)
        return wrapped
    def json_error(message, code): return jsonify({"error":message}), code
    def latest_observation(station_id):
        return EnvironmentalObservation.query.filter_by(station_id=station_id).order_by(desc(EnvironmentalObservation.observation_datetime)).first()
    def station_payload(station): return station.to_dict(latest_observation(station.station_id))
    def parse_station(data, station=None):
        required=["station_name","station_type","city","province","latitude","longitude"]
        missing=[k for k in required if data.get(k) in (None, "") and station is None]
        if missing: raise ValueError("Missing required fields: " + ", ".join(missing))
        def val(key, default=None): return data.get(key, getattr(station,key,default) if station else default)
        name=str(val("station_name", "")).strip(); city=str(val("city", "")).strip(); province=str(val("province", "")).strip()
        stype=val("station_type", "Weather Station"); status=val("status", "Active")
        try: lat=float(val("latitude")); lon=float(val("longitude"))
        except (TypeError,ValueError): raise ValueError("Latitude and longitude must be numbers")
        if not name or not city or not province: raise ValueError("Station name, city and province cannot be empty")
        if stype not in ("Weather Station","Rain Gauge","Air Quality Station"): raise ValueError("Invalid station type")
        if status not in ("Active","Inactive"): raise ValueError("Status must be Active or Inactive")
        if not -90 <= lat <= 90 or not -180 <= lon <= 180: raise ValueError("Coordinates are out of range")
        dateval=val("installation_date")
        try: install_date=datetime.strptime(dateval,"%Y-%m-%d").date() if dateval else None
        except ValueError: raise ValueError("Installation date must use YYYY-MM-DD")
        return dict(station_name=name,station_type=stype,city=city,province=province,latitude=lat,longitude=lon,location=WKTElement(f"POINT({lon} {lat})",srid=4326),installation_date=install_date,status=status,description=str(val("description", "") or "").strip(),data_source=str(val("data_source", "Student demonstration dataset") or "Student demonstration dataset").strip(),is_demo=bool(val("is_demo", True)))
    def parse_observation(data, obs=None):
        sid=data.get("station_id", obs.station_id if obs else None)
        try: sid=int(sid)
        except (TypeError,ValueError): raise ValueError("A valid station_id is required")
        if not db.session.get(MonitoringStation,sid): raise ValueError("Station does not exist")
        dt=data.get("observation_datetime")
        if not dt and obs: dt=obs.observation_datetime.isoformat()
        try:
            parsed=datetime.fromisoformat(str(dt).replace("Z","+00:00"))
            if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=timezone.utc)
        except (ValueError,TypeError): raise ValueError("observation_datetime must be ISO 8601")
        fields={"temperature_celsius":(-90,65),"humidity_percent":(0,100),"rainfall_mm":(0,None),"pm25_ug_m3":(0,None),"pm10_ug_m3":(0,None),"air_quality_index":(0,None),"wind_speed_kmh":(0,None)}
        result={"station_id":sid,"observation_datetime":parsed,"observation_source":str(data.get("observation_source", obs.observation_source if obs else "Simulated demonstration reading")),"is_demo":bool(data.get("is_demo", obs.is_demo if obs else True))}
        for key,(lo,hi) in fields.items():
            raw=data.get(key, getattr(obs,key,None) if obs else None)
            if raw in (None,""): result[key]=None; continue
            try: value=float(raw)
            except (TypeError,ValueError): raise ValueError(f"{key} must be numeric")
            if value < lo or (hi is not None and value > hi): raise ValueError(f"{key} is outside the allowed range")
            result[key]=int(value) if key=="air_quality_index" else value
        if all(result[k] is None for k in fields): raise ValueError("At least one measurement must be provided")
        return result

    @app.get("/")
    def index(): return render_template("index.html")
    @app.get("/login")
    def login(): return render_template("login.html")
    @app.post("/login")
    def login_post():
        username=request.form.get("username", "").strip(); password=request.form.get("password", "")
        user=User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user); flash("Signed in successfully.","success"); return redirect(request.args.get("next") or url_for("index"))
        flash("Invalid username or password.","danger"); return redirect(url_for("login"))
    @app.post("/logout")
    @login_required
    def logout(): logout_user(); flash("You have been signed out.","info"); return redirect(url_for("index"))
    @app.get("/api/me")
    def me(): return jsonify({"authenticated":current_user.is_authenticated,"username":current_user.username if current_user.is_authenticated else None,"role":current_user.role if current_user.is_authenticated else None})

    @app.get("/api/stations")
    def get_stations():
        q=MonitoringStation.query
        for arg,col in (("city",MonitoringStation.city),("station_type",MonitoringStation.station_type),("status",MonitoringStation.status)):
            value=request.args.get(arg)
            if value and value != "all": q=q.filter(col==value)
        search=request.args.get("search","").strip()
        if search: q=q.filter(db.or_(MonitoringStation.station_name.ilike(f"%{search}%"),MonitoringStation.city.ilike(f"%{search}%"),MonitoringStation.province.ilike(f"%{search}%")))
        try: page=max(1,int(request.args.get("page",1))); per_page=min(100,max(1,int(request.args.get("per_page",100))))
        except ValueError: return json_error("page and per_page must be integers",400)
        total=q.count(); stations=q.order_by(MonitoringStation.station_name).offset((page-1)*per_page).limit(per_page).all()
        return jsonify({"items":[station_payload(s) for s in stations],"total":total,"page":page,"per_page":per_page})
    @app.get("/api/stations/geojson")
    def stations_geojson():
        # ST_AsGeoJSON is used explicitly so the spatial database generates geometry.
        q=MonitoringStation.query
        for arg,col in (("city",MonitoringStation.city),("station_type",MonitoringStation.station_type),("status",MonitoringStation.status)):
            value=request.args.get(arg)
            if value and value!="all": q=q.filter(col==value)
        search=request.args.get("search","").strip()
        if search: q=q.filter(db.or_(MonitoringStation.station_name.ilike(f"%{search}%"),MonitoringStation.city.ilike(f"%{search}%")))
        rows=db.session.query(MonitoringStation,func.ST_AsGeoJSON(MonitoringStation.location)).filter(MonitoringStation.station_id.in_([s.station_id for s in q.all()])).all()
        import json
        features=[]
        for s,geom in rows:
            latest=latest_observation(s.station_id)
            features.append({"type":"Feature","geometry":json.loads(geom),"properties":{**s.to_dict(latest),"station_id":s.station_id}})
        return jsonify({"type":"FeatureCollection","features":features})
    @app.get("/api/stations/<int:station_id>")
    def get_station(station_id):
        s=db.session.get(MonitoringStation,station_id)
        if not s: return json_error("Station not found",404)
        return jsonify(station_payload(s))
    @app.post("/api/stations")
    @editor_required
    def create_station():
        try: s=MonitoringStation(**parse_station(request.get_json(silent=True) or {})); db.session.add(s); db.session.flush(); db.session.commit(); return jsonify(station_payload(s)),201
        except ValueError as e: db.session.rollback(); return json_error(str(e),400)
        except Exception: db.session.rollback(); app.logger.exception("Station creation failed"); return json_error("Could not create station",500)
    @app.put("/api/stations/<int:station_id>")
    @editor_required
    def update_station(station_id):
        s=db.session.get(MonitoringStation,station_id)
        if not s: return json_error("Station not found",404)
        try:
            for k,v in parse_station(request.get_json(silent=True) or {},s).items(): setattr(s,k,v)
            db.session.commit(); return jsonify(station_payload(s))
        except ValueError as e: db.session.rollback(); return json_error(str(e),400)
        except Exception: db.session.rollback(); app.logger.exception("Station update failed"); return json_error("Could not update station",500)
    @app.delete("/api/stations/<int:station_id>")
    @admin_required
    def delete_station(station_id):
        s=db.session.get(MonitoringStation,station_id)
        if not s: return json_error("Station not found",404)
        db.session.delete(s); db.session.commit(); return jsonify({"message":"Station and related observations deleted"})

    @app.get("/api/observations")
    def get_observations():
        q=EnvironmentalObservation.query
        sid=request.args.get("station_id")
        if sid:
            try: q=q.filter_by(station_id=int(sid))
            except ValueError: return json_error("station_id must be an integer",400)
        start=request.args.get("start"); end=request.args.get("end")
        try:
            if start: q=q.filter(EnvironmentalObservation.observation_datetime>=datetime.fromisoformat(start.replace("Z","+00:00")))
            if end: q=q.filter(EnvironmentalObservation.observation_datetime<=datetime.fromisoformat(end.replace("Z","+00:00")))
        except ValueError: return json_error("start/end must be ISO dates or ISO datetimes",400)
        try: limit=min(500,max(1,int(request.args.get("limit",100))))
        except ValueError: return json_error("limit must be an integer",400)
        rows=q.order_by(desc(EnvironmentalObservation.observation_datetime)).limit(limit).all()
        return jsonify({"items":[o.to_dict() for o in rows],"count":len(rows)})
    @app.get("/api/stations/<int:station_id>/observations")
    def station_observations(station_id):
        if not db.session.get(MonitoringStation,station_id): return json_error("Station not found",404)
        rows=EnvironmentalObservation.query.filter_by(station_id=station_id).order_by(desc(EnvironmentalObservation.observation_datetime)).limit(500).all()
        return jsonify({"items":[o.to_dict() for o in rows],"count":len(rows)})
    @app.post("/api/observations")
    @editor_required
    def create_observation():
        try: o=EnvironmentalObservation(**parse_observation(request.get_json(silent=True) or {})); db.session.add(o); db.session.commit(); return jsonify(o.to_dict()),201
        except ValueError as e: db.session.rollback(); return json_error(str(e),400)
        except Exception: db.session.rollback(); app.logger.exception("Observation creation failed"); return json_error("Could not create observation",500)
    @app.put("/api/observations/<int:observation_id>")
    @editor_required
    def update_observation(observation_id):
        o=db.session.get(EnvironmentalObservation,observation_id)
        if not o: return json_error("Observation not found",404)
        try:
            for k,v in parse_observation(request.get_json(silent=True) or {},o).items(): setattr(o,k,v)
            db.session.commit(); return jsonify(o.to_dict())
        except ValueError as e: db.session.rollback(); return json_error(str(e),400)
        except Exception: db.session.rollback(); app.logger.exception("Observation update failed"); return json_error("Could not update observation",500)
    @app.delete("/api/observations/<int:observation_id>")
    @admin_required
    def delete_observation(observation_id):
        o=db.session.get(EnvironmentalObservation,observation_id)
        if not o: return json_error("Observation not found",404)
        db.session.delete(o); db.session.commit(); return jsonify({"message":"Observation deleted"})

    @app.get("/api/statistics")
    def statistics():
        counts={r[0]:r[1] for r in db.session.query(MonitoringStation.station_type,func.count()).group_by(MonitoringStation.station_type).all()}
        total=MonitoringStation.query.count(); active=MonitoringStation.query.filter_by(status="Active").count()
        obs=EnvironmentalObservation.query.order_by(EnvironmentalObservation.observation_datetime).all()
        def series(key): return [{"date":o.observation_datetime.isoformat(),"value":getattr(o,key)} for o in obs if getattr(o,key) is not None]
        cities=[{"city":r[0],"count":r[1]} for r in db.session.query(MonitoringStation.city,func.count()).group_by(MonitoringStation.city).order_by(desc(func.count())).all()]
        return jsonify({"total_stations":total,"active_stations":active,"weather_stations":counts.get("Weather Station",0),"rain_gauges":counts.get("Rain Gauge",0),"air_quality_stations":counts.get("Air Quality Station",0),"demo_stations":MonitoringStation.query.filter_by(is_demo=True).count(),"temperature":series("temperature_celsius"),"rainfall":series("rainfall_mm"),"pm25":series("pm25_ug_m3"),"aqi":series("air_quality_index"),"cities":cities,"data_notice":"Seed observations are simulated demonstration data, not official or real-time measurements."})

    @app.get("/api/spatial/nearby")
    def nearby():
        try: lat=float(request.args["lat"]); lon=float(request.args["lon"]); radius=float(request.args.get("radius_m",25000))
        except (KeyError,ValueError): return json_error("lat and lon are required numbers; radius_m is optional",400)
        if not -90<=lat<=90 or not -180<=lon<=180 or not 0<radius<=500000: return json_error("Coordinates or radius out of range (radius max 500000 m)",400)
        point=func.ST_SetSRID(func.ST_MakePoint(lon,lat),4326)
        rows=MonitoringStation.query.filter(func.ST_DWithin(func.Geography(MonitoringStation.location),func.Geography(point),radius)).all()
        return jsonify({"radius_m":radius,"items":[station_payload(s) for s in rows]})

    @app.cli.command("seed-demo")
    def seed_demo_command():
        from database.seed_data import seed
        seed()

    @app.cli.command("create-admin")
    def create_admin():
        """Create an administrator using interactive prompts."""
        import getpass
        username=input("Admin username: ").strip(); email=input("Admin email: ").strip(); password=getpass.getpass("Password (12+ chars recommended): ")
        if len(password)<12: print("Password must be at least 12 characters."); return
        if User.query.filter(db.or_(User.username==username,User.email==email)).first(): print("Username or email already exists."); return
        u=User(username=username,email=email,role="Admin"); u.set_password(password); db.session.add(u); db.session.commit(); print("Administrator created.")
    @app.cli.command("init-db")
    def init_db():
        with db.engine.begin() as conn: conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        db.create_all()
        print("PostGIS extension and application tables are ready.")
    return app

app=create_app()
if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG",False), host="127.0.0.1", port=5000)
