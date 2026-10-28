# Pakistan Environmental Monitoring Web GIS

A database-driven university lab project using Flask, PostgreSQL/PostGIS, GeoJSON, Leaflet, Bootstrap, and Chart.js. **The included stations are representative demonstration locations and all seeded observations are simulated. They are not official monitoring stations, real measurements, or real-time data.**

## 1. Problem statement and objectives
Environmental datasets are easier to inspect when station records, observations, and spatial locations are managed together. This application demonstrates a central database for station inventory, spatial exploration, observations, charts, search/filtering, and controlled CRUD operations.

## 2. Study area
Ten representative cities are included: Islamabad, Rawalpindi, Lahore, Karachi, Peshawar, Quetta, Multan, Faisalabad, Murree, and Abbottabad. Coordinates are city-centred reference points with small offsets for demo markers, not verified station coordinates.

## 3. Technologies
- Python 3.11+; Flask; Flask-SQLAlchemy; Flask-Login; Flask-WTF CSRF; Flask-CORS
- PostgreSQL 14+ with PostGIS 3+
- GeoAlchemy2 and psycopg 3
- HTML5/CSS3/JavaScript, Bootstrap 5, Leaflet, Leaflet.markercluster, Chart.js
- OpenStreetMap tiles (requires internet access)

## 4. Architecture
Browser UI → same-origin Flask routes / JSON REST API → SQLAlchemy / GeoAlchemy2 → PostgreSQL/PostGIS. Station geometry is stored as `geometry(Point,4326)`. The GeoJSON endpoint uses `ST_AsGeoJSON`; the nearby-search endpoint uses `ST_DWithin` against geography in metres. Charts and statistic cards are populated from `/api/statistics`, not frontend hardcoded measurement arrays.

## 5. Project structure
```
environmental-monitoring-gis/
├── app.py                 # Flask application, REST API and CLI commands
├── app_extensions.py      # SQLAlchemy extension
├── config.py              # environment-backed configuration
├── models.py              # users, stations, observations and constraints
├── requirements.txt
├── .env.example
├── database/
│   ├── schema.sql
│   └── seed_data.py
├── routes/                # reserved for future route blueprints
├── templates/             # dashboard and login pages
├── static/css/style.css
├── static/js/              # dashboard, map, CRUD and charts
└── tests/test_api.py
```

## 6. Database schema and relationships
- `users`: unique username/email, password hash, role (`Admin` or `Viewer`)
- `monitoring_stations`: station attributes, latitude/longitude, PostGIS point, status and data provenance
- `environmental_observations`: nullable sensor measurements, timestamp, source and `station_id` foreign key
- One station has many observations. Deleting a station deletes its observations.
- Check constraints validate station type/status, coordinate ranges and measurement ranges. Spatial GiST index supports spatial lookups; observation indexes support station/time retrieval.

### ER diagram
```mermaid
erDiagram
  USERS {
    int user_id PK
    string username UK
    string email UK
    string password_hash
    string role
  }
  MONITORING_STATIONS {
    int station_id PK
    string station_name
    string station_type
    string city
    string province
    float latitude
    float longitude
    geometry location
    string status
    boolean is_demo
  }
  ENVIRONMENTAL_OBSERVATIONS {
    int observation_id PK
    int station_id FK
    datetime observation_datetime
    float temperature_celsius
    float rainfall_mm
    float pm25_ug_m3
    int air_quality_index
    boolean is_demo
  }
  MONITORING_STATIONS ||--o{ ENVIRONMENTAL_OBSERVATIONS : records
```

## 7. Windows setup (VS Code)

### A. Install prerequisites
1. Install Python 3.11 or newer and PostgreSQL. During PostgreSQL setup, remember the database superuser password.
2. Ensure PostGIS is installed for your PostgreSQL version (Stack Builder can install it on Windows). If `CREATE EXTENSION postgis` fails, install PostGIS first.
3. Open this folder in VS Code. Open Terminal → New Terminal.

### B. Create database
In pgAdmin Query Tool connected to the PostgreSQL server, run:
```sql
CREATE DATABASE environmental_monitoring_db;
```
Then connect to `environmental_monitoring_db` and run:
```sql
CREATE EXTENSION IF NOT EXISTS postgis;
SELECT PostGIS_Full_Version();
```

### C. Configure Python
PowerShell terminal from the project directory:
```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```
Edit `.env`: set a long random `SECRET_KEY` and your actual PostgreSQL password in `DATABASE_URL`. Example format:
`postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/environmental_monitoring_db`
If your password includes special characters, URL-encode them.

### D. Create tables and seed data
```powershell
flask --app app init-db
python database/seed_data.py
```
Seeding is idempotent in the simple sense that it skips if stations already exist. To reseed, back up first, then delete the demo stations/observations intentionally from pgAdmin and rerun.

### E. Create an administrator
```powershell
flask --app app create-admin
```
Choose a unique username/email and a strong password of at least 12 characters. No default admin password is provided. Viewers can inspect data without logging in; only Admin can create/update records; only Admin can delete records. There is no public signup endpoint.

### F. Run locally
```powershell
flask --app app run --debug
```
Open http://127.0.0.1:5000. Leave the terminal running. For a normal non-debug run, omit `--debug`. Never use Flask's development server as a public production server.

## 8. REST API reference
All responses are JSON except HTML pages. Modifying API calls require a logged-in Admin session and a valid CSRF token (`X-CSRFToken` header for fetch requests). Delete routes require Admin. HTTP 400 indicates invalid input, 401 login-required, 403 insufficient role, and 404 missing record.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/me` | Current session and role |
| GET | `/api/stations` | List/filter/paginate stations (`city`, `station_type`, `status`, `search`, `page`, `per_page`) |
| GET | `/api/stations/<id>` | Station plus latest observation if present |
| POST | `/api/stations` | Create station (Admin) |
| PUT | `/api/stations/<id>` | Update station (Admin) |
| DELETE | `/api/stations/<id>` | Delete station and observations (Admin) |
| GET | `/api/stations/geojson` | GeoJSON FeatureCollection, database geometry via `ST_AsGeoJSON` |
| GET | `/api/observations` | List observations (`station_id`, `start`, `end`, `limit`) |
| GET | `/api/stations/<id>/observations` | Station history |
| POST | `/api/observations` | Create observation (Admin) |
| PUT | `/api/observations/<id>` | Update observation (Admin) |
| DELETE | `/api/observations/<id>` | Delete observation (Admin) |
| GET | `/api/statistics` | Station counts and chart series |
| GET | `/api/spatial/nearby?lat=33.68&lon=73.05&radius_m=25000` | Spatial radius query using `ST_DWithin` |

Example station JSON for POST:
```json
{
  "station_name": "Campus Weather Demo",
  "station_type": "Weather Station",
  "city": "Islamabad",
  "province": "Islamabad Capital Territory",
  "latitude": 33.6844,
  "longitude": 73.0479,
  "status": "Active",
  "data_source": "Student demonstration dataset",
  "is_demo": true
}
```

## 9. Main features
- Interactive Pakistan map with clustered, type-coloured markers, popups, scale, legend, and map-click coordinate selection in the station form.
- City, type, status, and text filters; fit-to-results; CSV and GeoJSON exports.
- Station details and observation history; charts sourced from database API.
- Station and observation CRUD, server-side validation, password hashing, session authentication, role checks, CSRF protection, and environment configuration.
- Spatial query endpoint for nearby stations.

## 10. Testing
Set `DATABASE_URL` to a disposable PostgreSQL/PostGIS test database, install dependencies, then run:
```powershell
pip install pytest
pytest -q
```
The tests are integration-oriented and need PostGIS. Do not point tests at a database containing important data. Manual demo checklist: map loads; filters change map/table; stats/charts load; login as Admin; add/edit station; add observation; refresh and verify; delete a station only after confirmation; verify Viewer receives 403 for modification attempts.

## 11. Limitations and future improvements
- Seeded station points and observations are simulated and explicitly labelled. There is no sensor ingest, official data feed, or real-time guarantee.
- CDN libraries and OpenStreetMap tiles need internet access.
- This lab build uses a single Flask module for the API to keep local setup simple; `routes/` is retained for a future blueprint refactor.
- For production, add rate limiting, audit logs, backups, HTTPS, hardened deployment, stronger monitoring, more granular permissions, and verified data ingestion/licensing.
