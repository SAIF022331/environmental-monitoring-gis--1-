"""Seed 30 clearly-labelled demo stations and 3 simulated observations per station.
Run: flask --app app seed-demo (or python database/seed_data.py after configuring env).
"""
from datetime import date, datetime, timedelta, timezone
import random
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from geoalchemy2.elements import WKTElement
from app import create_app
from app_extensions import db
from models import MonitoringStation, EnvironmentalObservation

CITIES=[("Islamabad","Islamabad Capital Territory",33.6844,73.0479),("Rawalpindi","Punjab",33.5651,73.0169),("Lahore","Punjab",31.5204,74.3587),("Karachi","Sindh",24.8607,67.0011),("Peshawar","Khyber Pakhtunkhwa",34.0151,71.5249),("Quetta","Balochistan",30.1798,66.9750),("Multan","Punjab",30.1575,71.5249),("Faisalabad","Punjab",31.4504,73.1350),("Murree","Punjab",33.9070,73.3943),("Abbottabad","Khyber Pakhtunkhwa",34.1688,73.2215)]
TYPES=["Weather Station","Rain Gauge","Air Quality Station"]

def seed():
    app=create_app()
    with app.app_context():
        with db.engine.begin() as conn: conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS postgis")
        db.create_all()
        if MonitoringStation.query.count(): print("Stations already exist; skipping seed to avoid duplicates."); return
        random.seed(20261028); now=datetime.now(timezone.utc)
        for ti,stype in enumerate(TYPES):
            for i,(city,province,lat,lon) in enumerate(CITIES):
                # Small offsets distinguish illustrative station points; these are not verified facility coordinates.
                slat=lat+(ti-1)*0.035+(i%3)*0.008; slon=lon+(ti-1)*0.04+(i%4)*0.009
                s=MonitoringStation(station_name=f"{city} {stype} Demo {i+1:02d}",station_type=stype,city=city,province=province,latitude=slat,longitude=slon,location=WKTElement(f"POINT({slon} {slat})",srid=4326),installation_date=date(2023,1,1)+timedelta(days=i*31),status="Inactive" if i==9 and ti==2 else "Active",description="Illustrative station for university lab demonstration; not an assertion of official operation.",data_source="Simulated demonstration dataset (not official / not real-time)",is_demo=True)
                db.session.add(s); db.session.flush()
                for j in range(3):
                    dt=now-timedelta(days=(2-j)*7+i%4)
                    o=EnvironmentalObservation(station_id=s.station_id,observation_datetime=dt,observation_source="Simulated demonstration reading (not measured)",is_demo=True)
                    if stype=="Weather Station": o.temperature_celsius=round(random.uniform(10,39),1); o.humidity_percent=round(random.uniform(20,85),1); o.wind_speed_kmh=round(random.uniform(1,28),1)
                    elif stype=="Rain Gauge": o.rainfall_mm=round(random.uniform(0,28),1); o.humidity_percent=round(random.uniform(30,90),1)
                    else: o.pm25_ug_m3=round(random.uniform(8,155),1); o.pm10_ug_m3=round(random.uniform(20,230),1); o.air_quality_index=random.randint(20,220)
                    db.session.add(o)
        db.session.commit(); print("Seeded 30 demo stations and 90 simulated observations.")

if __name__=="__main__": seed()
