# Panda Smart backend

Django 5 + Django REST Framework implementation of the contract in
`../architecture.md`, guided by `../Panda_Smart_Project_Overview.docx`.

The demo seeds wards in both **south-eastern Kenya** (Kitui, Makueni, Machakos)
and the **metropolitan region** (Nairobi, Mombasa). The API itself is
ward-agnostic; region is an optional `Ward` field used by the rules engine.

## Setup

This machine has Python 3.14; Django 5.2 and DRF run on it. A local virtual
environment is included at `.venv`.

```bash
# from the backend folder of the repo
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py seed_demo
.venv\Scripts\python.exe manage.py runserver
```

Copy `.env.example` to `.env` and set `SECRET_KEY` before any non-local use.
`.env` is loaded automatically via `python-dotenv`; real environment variables
take precedence. Nothing secret is committed.

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django signing key |
| `DEBUG` | `1` for local development |
| `ALLOWED_HOSTS` | Comma-separated hostnames |
| `DATABASE_URL` | `sqlite:///...` locally, `postgresql://...` in deployment |
| `CORS_ALLOWED_ORIGINS` | Comma-separated frontend origins |
| `FRONTEND_BASE_URL` | Base URL for farmer verification links (default `http://127.0.0.1:5500`, the HTML frontend) |
| `FRONTEND_VERIFY_PATH` | Path before the token in verification links (default `/verify.html?token=`) |
| `SELF_REGISTER_TENANT` | Cooperative name for self-registered farmers (default: the oldest cooperative) |
| `VERIFY_TOKEN_TTL_DAYS` | Verification link lifetime (default 14) |
| `AT_USERNAME`, `AT_API_KEY` | Africa's Talking sandbox settings (simulator only) |
| `USSD_CALLBACK_SECRET` | Shared secret for the USSD callback URL (`?key=`); required when `DEBUG=0` |
| `TOKEN_TTL_HOURS` | Sign-in token lifetime in hours (default 168; 0 = never expire) |
| `LOGIN_PHONE_RATE` | Sign-in attempts allowed per phone number (default `20/hour`) |
| `RAINFALL_SOURCE_PRIORITY` | Rainfall source order for advice (default `NASA_POWER,CHIRPS`) |
| `OPEN_METEO_ENABLED` | `1` to show forecasts (Open-Meteo free tier is non-commercial only) |

For PostgreSQL, install a driver too: `pip install "psycopg[binary]>=3"`.

## Demo logins

Password for all: `demo1234`.

| Login phone | Role |
|---|---|
| `+254700000001` | Storage agent (`agent@demo`) |
| `+254700000002` | Storage agent |
| `+254700000003` | Cooperative admin (`coop@demo`) |
| `+254700000004` | Admin |
| `+254700000005` | Farmer (`farmer@demo`) |

## API

- Base URL: `http://localhost:8000/api/v1/`
- Swagger UI: `http://localhost:8000/api/docs/`
- Schema: `http://localhost:8000/api/schema/`
- Committed schema: `../openapi.yaml` (regenerate with
  `manage.py spectacular --file ../openapi.yaml` after API changes)

All non-2xx responses use the agreed envelope:

```json
{"error": {"code": "validation_error", "message": "...", "fields": {}}}
```

Auth is `Authorization: Token <key>` except `/auth/login/`, `/verify/*` and
`/ussd/`. Public endpoints are rate limited.

## Frontend integration

The working frontend is the plain HTML app in `../frontend/html/` (see its
README). Serve it with `python -m http.server 5500 --bind 127.0.0.1` and run
Django on `127.0.0.1:8000`. Port 5500 is in the default `CORS_ALLOWED_ORIGINS`,
and farmer verification links default to
`http://127.0.0.1:5500/verify.html?token=<token>` (`FRONTEND_BASE_URL`,
`FRONTEND_VERIFY_PATH`).

The React/Vite folder `../frontend/panda-smart-frontend/` is an unfinished
shell. If it is revived, set `FRONTEND_BASE_URL=http://localhost:5173` and
`FRONTEND_VERIFY_PATH=/verify/`.

Notes for the contract boundary:

- `GET /wards/` and `GET /crops/` are DRF-paginated (`count`/`results`); the
  frontend unwraps `results`.
- `GET /dashboard/wards/` returns ward summaries; the frontend fetches
  `GET /dashboard/wards/{id}/` per ward to render per-crop rows.
- Verification links use `FRONTEND_BASE_URL`, so they open the local
  `/verify/<token>` route by default.
- `POST /lots/` and `POST /planting-intents/` take `farmer_id`/`plot_id` in JSON;
  the views translate those to model instances for the service layer.

## Apps and integration

- `core/` — users, roles, tenants, wards, crops, farmers, plots, auth.
- `records/` (Backend A in the architecture) — lots, append-only events with a
  SHA-256 hash chain, loss calculation, verification links, stock service.
- `planting/` (Backend B) — rules-based advice, intents and slot allocation,
  USSD simulator, ward dashboard.
- `seed/` — `seed_demo` command and CHIRPS-style price/rainfall fixtures.

Cross-app access goes through service functions only. The dashboard calls
`records.services.get_stock_by_ward(ward_id, crop)`, which returns
`{stored_kg, avg_loss_pct, lot_count}`.

## Tests and quality checks

```bash
.venv\Scripts\python.exe manage.py test
.venv\Scripts\python.exe manage.py check
```

The suite covers the architecture's minimum set: loss calculation, append-only
enforcement, hash-chain validity, oversubscription, tenant isolation, verify
token expiry, plus dashboard privacy suppression and the USSD menu flow.

## Management commands

- `manage.py seed_demo` — idempotent demo data (6 wards, 30 farmers, 15 lots,
  102 planting intents, rainfall and price series).
- `manage.py import_rainfall <csv>` — import `ward_name,date,rainfall_mm[,source][,county]`.
- `manage.py fetch_rainfall [--days 60] [--ward NAME]` — daily rainfall from NASA POWER
  (free, no key) for wards with coordinates. Needs internet.

## Notes

- Lot events are immutable: `save()` and `delete()` raise; corrections are new
  `CORRECTION` events. Database-level permission hardening is deferred until
  PostgreSQL is used in deployment.
- Dashboard numbers are suppressed when a ward has fewer than five farmers for
  a crop (`"suppressed": true`, numeric fields `null`).
- USSD responses are plain text starting with `CON ` or `END `; sessions are
  stored in `UssdSession` and use the same services as the REST views.
- Watermelon is included for planting advice but is not storable, as required
  by the overview's scope boundaries.
