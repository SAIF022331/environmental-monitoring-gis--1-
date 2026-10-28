"""Integration tests. Configure DATABASE_URL to a disposable PostGIS test database first."""
import os
import pytest
from app import create_app
from app_extensions import db
from models import User, MonitoringStation
from geoalchemy2.elements import WKTElement

@pytest.fixture()
def app():
    if not os.getenv("DATABASE_URL"):
        pytest.skip("Set DATABASE_URL to a disposable PostgreSQL/PostGIS test database")
    app=create_app({"TESTING":True,"WTF_CSRF_ENABLED":False,"SECRET_KEY":"test-secret"})
    with app.app_context():
        db.drop_all(); db.create_all()
        with db.engine.begin() as conn: conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS postgis")
        u=User(username="testadmin",email="testadmin@example.test",role="Admin");u.set_password("test-password-123");db.session.add(u)
        s=MonitoringStation(station_name="Test Station",station_type="Weather Station",city="Islamabad",province="ICT",latitude=33.6844,longitude=73.0479,location=WKTElement("POINT(73.0479 33.6844)",srid=4326),status="Active",data_source="Test",is_demo=True);db.session.add(s);db.session.commit()
        yield app
        db.session.remove();db.drop_all()

@pytest.fixture()
def client(app): return app.test_client()

def login(client):
    with client.session_transaction() as sess: sess["_user_id"]="1";sess["_fresh"]=True

def test_stations_list(client):
    r=client.get('/api/stations');assert r.status_code==200;assert r.json['total']==1;assert r.json['items'][0]['station_name']=='Test Station'

def test_geojson(client):
    r=client.get('/api/stations/geojson');assert r.status_code==200;assert r.json['type']=='FeatureCollection';assert r.json['features'][0]['geometry']['type']=='Point'

def test_create_requires_auth(client):
    r=client.post('/api/stations',json={"station_name":"New","station_type":"Weather Station","city":"Lahore","province":"Punjab","latitude":31.5,"longitude":74.3});assert r.status_code in (401,302)

def test_admin_can_create_station(client):
    login(client);r=client.post('/api/stations',json={"station_name":"New Demo","station_type":"Rain Gauge","city":"Lahore","province":"Punjab","latitude":31.5,"longitude":74.3});assert r.status_code==201;assert r.json['station_name']=='New Demo'

def test_invalid_coordinates_rejected(client):
    login(client);r=client.post('/api/stations',json={"station_name":"Bad","station_type":"Weather Station","city":"Lahore","province":"Punjab","latitude":120,"longitude":74});assert r.status_code==400
