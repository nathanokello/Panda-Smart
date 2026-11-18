# Hifadhi Mavuno – GeoAgri implementation notes

## Audit outcome
The supplied codebase is Django + Django REST Framework, not FastAPI. It has SQLite development support and PostgreSQL URL support. Existing apps include `core`, `planting`, `records`, and `seed`. Existing farmer, ward, plot, crop, soil-test, rainfall, market-price, planting-intent, season, lot and lot-event records are retained.

## New files
- `backend/geoagri/` – additive Django application, models, serializers, API views, routes, cache helper, tests and README.
- `backend/geoagri/migrations/0001_initial.py` – GeoAgri schema.
- `frontend/html/geoagri.html` – GeoAgri page matching the existing shell and green visual language.
- `frontend/html/js/geoagri.js` – farm map, optional GPS, registration and intelligence panels.

## Modified files
- `backend/config/settings.py` – register `geoagri` app.
- `backend/config/urls.py` – include GeoAgri API routes.
- `frontend/html/js/ui.js` – add GeoAgri to the existing role-aware navigation.

## External services
Leaflet 1.9.4 and OpenStreetMap tiles are referenced by the browser page. Existing NASA POWER integration remains untouched. No new third-party agricultural API is activated in this pilot increment.

## Tests
GeoAgri API tests were added for authenticated farm listing, location-consent enforcement, missing crop requirements and ownership validation. They could not be executed in this environment because Django dependencies were not installed and package installation was blocked by unavailable network access. Run `python manage.py test geoagri` after installing `backend/requirements.txt`.

## Deployment
1. Install backend dependencies.
2. Configure `backend/.env` from `.env.example` with deployment-specific secrets; do not commit `.env`.
3. Run `python manage.py migrate` and `python manage.py check`.
4. Serve the existing `frontend/html` directory on an allowed frontend origin.
5. Ensure HTTPS for GPS and review OpenStreetMap tile usage requirements.

## Limitations / next stages
This is the first working foundation increment, not a claim that every requested external integration is complete. Polygon editing, offline sync, verified agronomic requirements, environmental provider adapters, KAMIS/buyer-demand ingestion, market forecasting, crop variety advice, full Kiswahili translation, and full lifecycle integration remain staged work. No unsupported soil readings, prices, suitability thresholds, yields or profits are invented.
