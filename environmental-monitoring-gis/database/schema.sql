-- Run while connected to environmental_monitoring_db as a database owner.
CREATE EXTENSION IF NOT EXISTS postgis;
-- Canonical ORM schema is defined in models.py; Flask CLI init-db creates tables.
-- This file documents the core spatial setup and can be used to verify installation.
SELECT PostGIS_Full_Version();
CREATE INDEX IF NOT EXISTS ix_monitoring_stations_location_gist
  ON monitoring_stations USING GIST (location);
CREATE INDEX IF NOT EXISTS ix_observations_station_datetime
  ON environmental_observations (station_id, observation_datetime DESC);
