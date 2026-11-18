# GeoAgri Intelligence (pilot foundation)

GeoAgri is an additive Django app. It reuses `core.Farmer`, `core.Plot`, and `core.Ward`; it does not create a second farmer identity or migrate historical farm records.

## Implemented in this increment

- Authenticated farm-profile API attached one-to-one to existing `Plot` records.
- Optional GPS coordinates and manual map-point selection in the HTML frontend.
- Explicit per-farm location consent before farm-specific environmental data can be read.
- Farm metadata: area unit, irrigation, water availability, known soil type, current crops.
- GeoJSON Polygon/MultiPolygon storage field for future boundary editing.
- Provenance-aware environmental observation model.
- Verified-source crop-requirement model and conservative suitability endpoint. No threshold is seeded without an agronomic source; absent data returns insufficient data rather than an invented result.
- Voluntary planting-intention aggregation endpoint that returns aggregates only.
- Six-hour cache helper for provider adapters.

## API

All routes are under `/api/v1/geoagri/` and require existing token authentication:

- `GET/POST farms/`
- `GET/PATCH/DELETE farms/{plot_uuid}/` (detail currently keyed by FarmProfile UUID)
- `GET farms/{plot_uuid}/environment/`
- `GET farms/{plot_uuid}/suitability/`
- `GET regional-supply/`
- `GET/POST planting-intents/`

Note: farm detail/environment/suitability route identifiers refer to the existing Plot UUID for environment and suitability. Farm profile detail uses its own profile UUID. Clients should use `plot_id` for environment/suitability and `id` for profile updates.

## Data-provider status

No external environmental or market provider is activated by this increment. The existing planting module's NASA POWER rainfall implementation remains unchanged. Provider integration must be separately implemented and verified before values are written into `EnvironmentalObservation`. Candidate sources named in the project brief include KMD, KALRO, CHIRPS, SoilGrids, FAO WaPOR, KAMIS and Open-Meteo; access, licensing, API stability and resolution need validation. Do not label gridded estimates as field measurements or lab soil tests.

## Security and consent

The API scopes farm access to the authenticated farmer, or to staff within their tenant (admins can access all). Farm-specific environmental retrieval checks `FarmProfile.location_consent`. GPS is invoked only after the user presses the GPS button; manual map selection is available. Regional aggregation includes only planting intentions with `share_for_aggregation=true` and exposes no farmer identity, farm ID or coordinates.

Before production, add an audited consent-revocation workflow, retention/deletion controls, rate limits for provider calls, encrypted backups, and review of Kenyan Data Protection Act obligations.

## Migrations and setup

```bash
cd backend
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py check
python manage.py test geoagri
```

Serve `frontend/html` on the configured frontend origin and set `API_BASE_URL` in `frontend/html/js/config.js`. Leaflet and OpenStreetMap tiles are loaded from their public CDN/tile service; comply with their current usage policies and do not bulk-download tiles.

## Known limitations

- Farm boundary GeoJSON is stored, but the current map UI captures a point only; polygon drawing/editing is a next increment.
- The pilot UI does not yet include a full offline queue/sync engine.
- No soil satellite provider, KMD forecast provider, CHIRPS adapter, KAMIS connector, market forecasting, price charts, buyer-demand ingestion, crop-variety catalogue or AI model is activated.
- No verified crop requirement thresholds are preloaded. Suitability therefore returns no recommendations until documented requirements and observations are supplied.
- Regional supply is a voluntary-intention aggregation, not total regional production. It must not be represented as such.
- OpenStreetMap tile availability is subject to its usage policy; production may require a compliant tile provider.
