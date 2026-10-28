from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from app_extensions import db

class User(UserMixin, db.Model):
    __tablename__ = "users"
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="Viewer")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.CheckConstraint("role IN ('Admin','Viewer')", name="ck_users_role"),)
    def get_id(self): return str(self.user_id)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class MonitoringStation(db.Model):
    __tablename__ = "monitoring_stations"
    station_id = db.Column(db.Integer, primary_key=True)
    station_name = db.Column(db.String(160), nullable=False)
    station_type = db.Column(db.String(30), nullable=False, index=True)
    city = db.Column(db.String(100), nullable=False, index=True)
    province = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    location = db.Column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False)
    installation_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(10), nullable=False, default="Active", index=True)
    description = db.Column(db.Text, nullable=True)
    data_source = db.Column(db.String(255), nullable=False, default="Student demonstration dataset")
    is_demo = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    observations = db.relationship("EnvironmentalObservation", back_populates="station", cascade="all, delete-orphan", lazy="select")
    __table_args__ = (
        db.CheckConstraint("station_type IN ('Weather Station','Rain Gauge','Air Quality Station')", name="ck_station_type"),
        db.CheckConstraint("status IN ('Active','Inactive')", name="ck_station_status"),
        db.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_station_latitude"),
        db.CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_station_longitude"),
        db.Index("ix_station_location_gist", "location", postgresql_using="gist"),
    )
    def to_dict(self, latest=None):
        return {"station_id":self.station_id,"station_name":self.station_name,"station_type":self.station_type,"city":self.city,"province":self.province,"latitude":self.latitude,"longitude":self.longitude,"installation_date":self.installation_date.isoformat() if self.installation_date else None,"status":self.status,"description":self.description,"data_source":self.data_source,"is_demo":self.is_demo,"created_at":self.created_at.isoformat() if self.created_at else None,"updated_at":self.updated_at.isoformat() if self.updated_at else None,"latest_observation":latest.to_dict() if latest else None}

class EnvironmentalObservation(db.Model):
    __tablename__ = "environmental_observations"
    observation_id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.Integer, db.ForeignKey("monitoring_stations.station_id", ondelete="CASCADE"), nullable=False, index=True)
    observation_datetime = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    temperature_celsius = db.Column(db.Float)
    humidity_percent = db.Column(db.Float)
    rainfall_mm = db.Column(db.Float)
    pm25_ug_m3 = db.Column(db.Float)
    pm10_ug_m3 = db.Column(db.Float)
    air_quality_index = db.Column(db.Integer)
    wind_speed_kmh = db.Column(db.Float)
    observation_source = db.Column(db.String(255), nullable=False, default="Simulated demonstration reading")
    is_demo = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    station = db.relationship("MonitoringStation", back_populates="observations")
    __table_args__ = (
        db.CheckConstraint("temperature_celsius IS NULL OR (temperature_celsius >= -90 AND temperature_celsius <= 65)", name="ck_obs_temp"),
        db.CheckConstraint("humidity_percent IS NULL OR (humidity_percent >= 0 AND humidity_percent <= 100)", name="ck_obs_humidity"),
        db.CheckConstraint("rainfall_mm IS NULL OR rainfall_mm >= 0", name="ck_obs_rainfall"),
        db.CheckConstraint("pm25_ug_m3 IS NULL OR pm25_ug_m3 >= 0", name="ck_obs_pm25"),
        db.CheckConstraint("pm10_ug_m3 IS NULL OR pm10_ug_m3 >= 0", name="ck_obs_pm10"),
        db.CheckConstraint("air_quality_index IS NULL OR air_quality_index >= 0", name="ck_obs_aqi"),
        db.CheckConstraint("wind_speed_kmh IS NULL OR wind_speed_kmh >= 0", name="ck_obs_wind"),
    )
    def to_dict(self):
        return {"observation_id":self.observation_id,"station_id":self.station_id,"station_name":self.station.station_name if self.station else None,"observation_datetime":self.observation_datetime.isoformat() if self.observation_datetime else None,"temperature_celsius":self.temperature_celsius,"humidity_percent":self.humidity_percent,"rainfall_mm":self.rainfall_mm,"pm25_ug_m3":self.pm25_ug_m3,"pm10_ug_m3":self.pm10_ug_m3,"air_quality_index":self.air_quality_index,"wind_speed_kmh":self.wind_speed_kmh,"observation_source":self.observation_source,"is_demo":self.is_demo,"created_at":self.created_at.isoformat() if self.created_at else None}
