# Panda Smart: Prototype Architecture

> Shared contract for backend and frontend. If the frontend follows Sections 4 to 7, it will plug into the backend without rework. If something here is wrong or missing, change this file in a pull request instead of working around it.

**Status:** Draft v1, demo prototype | **Scope:** MVP thin slice (see Project Overview, Section 3.4)

---

## 1. What we are building

A working web app that demonstrates the crop lifecycle for smallholder farmers:

| Stage | Module | Demo outcome |
|---|---|---|
| Plan | Planting Advice | Pick ward and crop, get a planting window with a probability |
| Coordinate | Planting Slots | Register intended acreage, get an oversubscription warning or an alternative crop |
| Store | Hifadhi Mavuno | Agent registers a grain lot and logs moisture and check-ups |
| Verify | Hifadhi Mavuno | Farmer confirms or disputes a record through a private link |
| Sell | Dashboard | Ward screen showing intended planting, stored stock and a sell-timing flag |

**Design principles**

1. **Simple first.** One backend, one database, one frontend. No microservices, no Celery, no ML.
2. **Records are append-only.** Lot history is never edited or deleted. Corrections are new events.
3. **Contract first.** The OpenAPI spec is the single source of truth between backend and frontend.
4. **Same logic for every channel.** The web app, the USSD simulator and SMS all call the same service functions.

---

## 2. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python 3.12, Django 5, Django REST Framework | Admin panel is used in the demo |
| Database | PostgreSQL 16 (SQLite allowed locally for the first days) | One `DATABASE_URL` setting switches it |
| Auth | DRF Token authentication | `Authorization: Token <key>` |
| API docs | drf-spectacular | Swagger UI at `/api/docs/`, schema at `/api/schema/` |
| SMS / USSD | Africa's Talking sandbox | Simulator only, no real phones for the demo |
| Scheduled jobs | Django management commands + cron | No Celery |
| Frontend | React 18 + Vite + TypeScript + Tailwind | Calls the REST API |
| Frontend data layer | TanStack Query + `openapi-typescript` | Types generated from the backend schema |
| Mocking | MSW or Prism against the OpenAPI file | Lets the frontend work before endpoints exist |
| Hosting | Render or Railway (backend + Postgres), Vercel or Netlify (frontend) | Deploy from GitHub |

---

## 3. System overview

```
 React web app (Vite)        USSD / SMS simulator (Africa's Talking)
        |                               |
        |  JSON over HTTPS              |  form-encoded POST
        v                               v
 +--------------------------------------------------------+
 |                 Django + DRF  (/api/v1/)               |
 |                                                        |
 |  core/       users, roles, wards, crops, farmers,      |
 |              plots, consent                            |
 |  records/    lots, lot events, verification, losses    |   <- Person A
 |  planting/   advice rules, intents, slots, dashboard,  |   <- Person B
 |              ussd, data ingestion                      |
 +--------------------------------------------------------+
                          |
                    PostgreSQL
```

Each app talks to the others only through **service functions** (for example `records.services.get_stock_by_ward(ward_id)`), never by importing each other's models directly in views. This keeps the two backend developers from stepping on each other.

---

## 4. Conventions (frontend and backend both follow these)

| Topic | Rule |
|---|---|
| Base URL | `{API_BASE_URL}/api/v1/` (frontend env var `VITE_API_BASE_URL`) |
| Format | JSON, `snake_case` keys |
| IDs | UUID strings |
| Dates | ISO 8601 in UTC, for example `2026-11-17T09:30:00Z`. Plain dates are `YYYY-MM-DD` |
| Units | Weight in **kg**, area in **acres**, moisture in **percent** (14.5 means 14.5%) |
| Auth header | `Authorization: Token <key>` on every request except login, `/verify/*` and `/ussd/` |
| Pagination | `?limit=20&offset=0`, response is `{count, next, previous, results}` |
| Filtering | Query params, for example `/lots/?ward=<id>&crop=green_gram&status=stored` |
| Errors | See below |
| CORS | Backend allows the frontend origin(s) from the `CORS_ALLOWED_ORIGINS` env var |

**Error shape (all non-2xx responses)**

```json
{
  "error": {
    "code": "validation_error",
    "message": "Moisture must be between 0 and 100.",
    "fields": { "moisture_pct": ["Must be between 0 and 100."] }
  }
}
```

Common codes: `validation_error` (400), `unauthenticated` (401), `forbidden` (403), `not_found` (404), `conflict` (409), `rate_limited` (429).

**Crop codes (fixed list):** `maize`, `green_gram`, `cowpea`, `watermelon`
**Roles:** `farmer`, `agent`, `coop_admin`, `admin`

---

## 5. Data model

### Core (shared, built together on day 1)

| Model | Key fields |
|---|---|
| `User` | id, phone, name, role, tenant (cooperative), password |
| `Tenant` | id, name, type (`cooperative`, `sacco`, `buyer`) |
| `Ward` | id, name, county, lat, lng |
| `Crop` | code, name_en, name_sw, storable (bool) |
| `Farmer` | id, user (optional), name, phone, ward, tenant, consent_given (bool), consent_at |
| `Plot` | id, farmer, ward, acres, lat, lng (optional) |

### Records app (Person A)

| Model | Key fields |
|---|---|
| `Lot` | id, farmer, agent, crop, ward, initial_weight_kg, location_label, registered_at, status (`stored`, `sold`, `disputed`, `closed`) |
| `LotEvent` | id, lot, type, payload (JSON), recorded_by, recorded_at, prev_hash, hash |
| `VerificationToken` | id, lot, farmer, token (signed, random), expires_at, used_at |

**`LotEvent.type` values and payloads**

| Type | Payload |
|---|---|
| `REGISTERED` | `{weight_kg, bag_count, storage_method}` |
| `MOISTURE_READING` | `{moisture_pct}` |
| `WEIGHT_READING` | `{weight_kg}` |
| `CHECKUP` | `{pest_signs: bool, notes}` |
| `LOSS_RECORDED` | `{loss_kg, cause}` |
| `VERIFIED` | `{method: "link" | "sms"}` |
| `DISPUTED` | `{reason}` |
| `CORRECTION` | `{corrects_event_id, new_payload, reason}` |

**Append-only rules**

- No `PUT`, `PATCH` or `DELETE` on events. Enforce in the view, the model (`save()` blocks updates) and the database permissions if you can.
- `hash = sha256(prev_hash + type + canonical_json(payload) + recorded_at)`. The first event of a lot has an empty `prev_hash`.
- `GET /lots/{id}/verify-chain/` recomputes the chain and returns `{valid: true|false}`. This is a good demo moment.

**Loss calculation (single definition, used everywhere)**

```
latest_weight_kg = payload.weight_kg of the latest WEIGHT_READING (else initial_weight_kg)
loss_kg          = initial_weight_kg - latest_weight_kg
loss_pct         = loss_kg / initial_weight_kg * 100
```

### Planting app (Person B)

| Model | Key fields |
|---|---|
| `AdviceRuleSet` | version, config (JSON), active (bool) |
| `RainfallObservation` | ward, date, rainfall_mm, source |
| `MarketPrice` | ward (or market), crop, date, price_per_kg_kes |
| `DemandEstimate` | ward, crop, season, expected_demand_acres |
| `PlantingIntent` | id, farmer, plot, crop, acres, season, slot (nullable), created_at |
| `Slot` | id, ward, crop, season, window_start, window_end, capacity_acres |

---

## 6. API contract

All paths are under `/api/v1/`. Request and response examples are the **agreed shapes**. Fields may be added later, never renamed or removed without telling the other side.

### 6.1 Auth and reference data (shared)

| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/auth/login/` | public | Phone + password, returns token. Accepts `0712…`, `254712…` or `+254712…` |
| POST | `/auth/logout/` | any | Deletes the caller's token (204) |
| POST | `/auth/register/farmer/` | public | Farmer self-registration `{name, phone, password, ward_id, consent_given}`; role is always `farmer`; returns `{token, user}` (201) |
| GET | `/auth/me/` | any | Current user and role; includes `farmer_id` for farmer logins |
| GET | `/wards/` | public | List wards (public so the sign-up form can load them) |
| GET | `/crops/` | public | List crops |
| GET, POST | `/farmers/` | agent, coop_admin | List or register a farmer |
| GET | `/farmers/{id}/` | agent, coop_admin, that farmer | Farmer detail |
| GET, POST | `/farmers/{id}/plots/` | agent, coop_admin, that farmer | Plots |
| GET | `/tenants/` | coop_admin (own), admin (all) | Cooperatives for the Users page |
| GET, POST | `/users/` | coop_admin, admin | Staff accounts. Coop admins see their cooperative and create agents only; admins manage all staff roles |
| GET, PATCH | `/users/{id}/` | coop_admin, admin | Change `name`, `role`, `tenant_id`, `is_active`, `password`. No DELETE: deactivate. Nobody edits their own account. Role, cooperative, password or status changes revoke the user's tokens |

Tokens expire after `TOKEN_TTL_HOURS` (default 168). Login is limited per IP and per phone number.

**Login**

```json
// POST /auth/login/
{ "phone": "+254700000001", "password": "demo1234" }

// 200
{
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b",
  "user": { "id": "uuid", "name": "Amina Mwende", "role": "agent", "tenant_id": "uuid" }
}
```

### 6.2 Storage and records (Person A)

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/lots/` | agent, coop_admin | List lots (filters: `ward`, `crop`, `status`, `farmer`) |
| POST | `/lots/` | agent | Register a lot (creates the `REGISTERED` event and a verification token) |
| GET | `/lots/{id}/` | agent, coop_admin | Lot detail with summary |
| GET | `/lots/{id}/events/` | agent, coop_admin | Event history, oldest first |
| POST | `/lots/{id}/events/` | agent | Add an event (moisture, weight, check-up, loss, correction) |
| GET | `/lots/{id}/verify-chain/` | agent, coop_admin | Hash chain integrity check |
| GET | `/verify/{token}/` | **public** | Farmer-facing lot summary and history |
| POST | `/verify/{token}/confirm/` | **public** | Farmer confirms the records |
| POST | `/verify/{token}/dispute/` | **public** | Farmer disputes, body `{reason}` |

**Register a lot**

```json
// POST /lots/
{
  "farmer_id": "uuid",
  "crop": "green_gram",
  "weight_kg": 500,
  "bag_count": 5,
  "storage_method": "hermetic_bag",
  "location_label": "Kitui Central store 2",
  "moisture_pct": 12.5
}

// 201
{
  "id": "uuid",
  "crop": "green_gram",
  "status": "stored",
  "initial_weight_kg": 500,
  "registered_at": "2026-11-17T09:30:00Z",
  "verification_url": "https://app.example.com/verify/Zk3...tokenA",
  "summary": { "latest_weight_kg": 500, "loss_kg": 0, "loss_pct": 0, "latest_moisture_pct": 12.5 }
}
```

**Add an event**

```json
// POST /lots/{id}/events/
{ "type": "MOISTURE_READING", "payload": { "moisture_pct": 13.8 } }

// 201
{
  "id": "uuid",
  "type": "MOISTURE_READING",
  "payload": { "moisture_pct": 13.8 },
  "recorded_by": { "id": "uuid", "name": "Amina Mwende" },
  "recorded_at": "2026-11-24T08:10:00Z",
  "hash": "a1b2..."
}
```

**Public verification page data**

```json
// GET /verify/{token}/
{
  "lot": { "id": "uuid", "crop": "green_gram", "initial_weight_kg": 500, "status": "stored" },
  "farmer_name": "Joseph Kioko",
  "events": [ { "type": "REGISTERED", "recorded_at": "...", "payload": { } } ],
  "summary": { "latest_weight_kg": 492, "loss_kg": 8, "loss_pct": 1.6 },
  "already_responded": false
}
```

Public verify endpoints reveal only that one lot, are rate limited, and the token expires (default 14 days) and is single-use for confirm or dispute.

`verification_url` points at the HTML frontend: `{FRONTEND_BASE_URL}{FRONTEND_VERIFY_PATH}{token}`, by default `http://127.0.0.1:5500/verify.html?token=<token>`. Set `FRONTEND_VERIFY_PATH=/verify/` for a frontend with path routing.

`summary` also carries `initial_weight_kg`. A `CORRECTION` whose `new_payload` has `weight_kg` or `moisture_pct` replaces that value of the corrected `REGISTERED`, `WEIGHT_READING` or `MOISTURE_READING` event in the summary; the original event is unchanged.

### 6.3 Planting (Person B)

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/advice/?ward={id}&crop={code}` | any | Planting window and confidence |
| POST | `/planting-intents/` | farmer, agent | Register intended crop and acres |
| GET | `/planting-intents/` | farmer (own only), agent, coop_admin | List intents (filters: `ward`, `crop`, `season`) |
| GET | `/wards/{id}/slots/?crop={code}` | any | Slot availability for a crop in a ward |
| GET, POST | `/farmers/{id}/seasons/` | that farmer, staff of the farmer's cooperative, admin | Season records: `season` (e.g. `2026-long-rains`), `crop`, `variety`, `acres`, `planted_on`, `methods`, `harvested_on`, `harvest_kg`, `outcome_notes`, optional `plot_id`; response adds `yield_kg_per_acre` |
| GET, PATCH | `/seasons/{id}/` | same | Add the harvest later or fix a typo (season records are planning notes, not proof, so they are editable) |
| GET, POST | `/farmers/{id}/soil-tests/` | same | `tested_on`, `source` (`lab`, `kit`, `extension_officer`, `other`), at least one of `ph`, `organic_carbon_pct`, `nitrogen_pct`, `phosphorus_ppm`, `potassium_ppm`; response adds `guidance` |
| GET | `/farmers/{id}/history/` | same | What worked before: per crop `seasons`, `avg_yield_kg_per_acre`, `best {season, variety, methods, yield_kg_per_acre}`, `storage_lots`, `avg_storage_loss_pct` (from records via `records.services.get_loss_by_crop_for_farmer`); plus `latest_soil_test` |
| GET | `/wards/{id}/weather/` | any | 7-day forecast `{enabled, ward, provider, attribution, days:[{date, rain_mm, temp_max_c, temp_min_c, rain_chance_pct}]}`; `{enabled:false}` unless `OPEN_METEO_ENABLED=1` (non-commercial licence) |

Advice uses rainfall from one source only, in `RAINFALL_SOURCE_PRIORITY` order (default NASA POWER, then CHIRPS), so the same rain is never counted twice. `python manage.py fetch_rainfall` loads NASA POWER data.

**Advice**

```json
// GET /advice/?ward=<id>&crop=green_gram
{
  "ward": { "id": "uuid", "name": "Kitui Central" },
  "crop": "green_gram",
  "recommended_window": { "start": "2026-11-25", "end": "2026-12-05" },
  "confidence": 0.7,
  "rationale": "Onset of rains expected in the last week of November.",
  "rule_set_version": "v3",
  "alternatives": ["cowpea"]
}
```

**Planting intent and oversubscription**

```json
// POST /planting-intents/
{ "farmer_id": "uuid", "plot_id": "uuid", "crop": "green_gram", "acres": 2.0, "season": "2026-short-rains" }

// 201
{
  "id": "uuid",
  "slot": { "id": "uuid", "window_start": "2026-12-01", "window_end": "2026-12-07" },
  "oversubscribed": true,
  "warning": "Green gram in this ward is above expected demand. You have been moved to a later window.",
  "alternatives": [ { "crop": "cowpea", "reason": "Lower planned acreage in your ward" } ]
}
```

### 6.4 Dashboard (Person B, reads from Person A through services)

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/dashboard/wards/` | coop_admin, admin | All wards, summary rows |
| GET | `/dashboard/wards/{id}/` | coop_admin, admin | One ward, per-crop detail |

```json
// GET /dashboard/wards/<id>/
{
  "ward": { "id": "uuid", "name": "Kitui Central" },
  "generated_at": "2026-11-17T10:00:00Z",
  "crops": [
    {
      "crop": "green_gram",
      "intended_acres": 120,
      "expected_demand_acres": 90,
      "oversubscription_pct": 33.3,
      "stored_stock_kg": 4200,
      "avg_loss_pct": 2.1,
      "latest_price_per_kg_kes": 95,
      "sell_flag": "hold",
      "sell_flag_reason": "Price is 12% below the 3-month average."
    }
  ]
}
```

`oversubscription_pct` = (intended − expected) ÷ expected × 100, never below 0 (120 against 90 gives 33.33).

`sell_flag` is one of `sell_now`, `hold`, `watch`. **Privacy rule:** if a ward has fewer than 5 farmers for a crop, return `null` for the numbers and add `"suppressed": true`.

### 6.5 USSD / SMS (Person B)

| Method | Path | Purpose |
|---|---|---|
| POST | `/ussd/` | Africa's Talking USSD callback (form-encoded: `sessionId`, `phoneNumber`, `text`) |

Response is plain text starting with `CON ` (continue) or `END ` (finish), at most 182 characters. When `USSD_CALLBACK_SECRET` is set, the callback URL must include `?key=<secret>`; with `DEBUG=0` the secret is required. (Menu 3 returns a farmer's private verify link, so an open endpoint would let anyone fetch it.) Session state is stored in a `UssdSession` table keyed by `sessionId`. Menu: 1) Planting advice, 2) My planting slot, 3) Verify my grain. Keep menus to three levels or fewer. USSD calls the same service functions as the REST views.

---

## 7. Frontend guide

> **Current frontend:** the plain HTML/CSS/JS app in `frontend/html/` implements every screen below (see its README). The React/Vite folder `frontend/panda-smart-frontend/` is an unfinished shell; the team should decide whether to keep it (Section 13).

### 7.1 Screens and the endpoints they use

| Screen | Role | Endpoints |
|---|---|---|
| Login | all | `POST /auth/login/`, `GET /auth/me/` |
| Farmer list and register | agent | `GET, POST /farmers/`, `GET /wards/` |
| Register lot | agent | `POST /lots/`, `GET /crops/` |
| Lot detail and timeline | agent | `GET /lots/{id}/`, `GET, POST /lots/{id}/events/`, `GET /lots/{id}/verify-chain/` |
| **Verify page (public, mobile first)** | farmer | `GET /verify/{token}/`, `POST /verify/{token}/confirm/`, `POST /verify/{token}/dispute/` |
| Planting advice | farmer, agent | `GET /advice/` |
| Register planting intent | farmer, agent | `POST /planting-intents/`, `GET /wards/{id}/slots/` |
| **Ward dashboard (demo centerpiece)** | coop_admin | `GET /dashboard/wards/`, `GET /dashboard/wards/{id}/` |

The public verify page lives at the route `/verify/:token`. It must work without login and look good on a small phone screen.

### 7.2 Setup

```bash
# Generate TypeScript types from the backend schema
npx openapi-typescript http://localhost:8000/api/schema/ -o src/api/schema.d.ts
```

- Keep one API client file (`src/api/client.ts`) that adds the token header, parses the error shape in Section 4, and redirects to login on 401.
- Store the token in memory plus `localStorage` for the demo. Do not put it in URLs.
- Use TanStack Query for fetching and caching. Show loading and error states on every screen.
- Env vars: `VITE_API_BASE_URL=http://localhost:8000`.

### 7.3 Working before the backend is ready

1. Backend publishes the OpenAPI file (`openapi.yaml`) in the repo on day 1 with example responses taken from Section 6.
2. Frontend runs a mock server against it: `npx prism mock openapi.yaml`, or MSW handlers copied from the examples.
3. When a real endpoint lands, switch the base URL. Nothing else should change. If something must change, the contract was wrong: update this file.

### 7.4 UI rules that protect the trust story

- Show the **loss figure and its formula** on the lot screen, not just a number.
- Event timelines are read-only. Corrections use an "Add correction" form that creates a new event.
- Show the verify status badge (`Awaiting farmer`, `Verified`, `Disputed`) on every lot.
- Support Swahili and English labels from the start (`name_sw`, `name_en` come from the API). Use an i18n file, not hard-coded text.

---

## 8. Repository layout

```
panda-smart/
  architecture.md
  openapi.yaml                # exported schema, committed
  backend/
    manage.py
    config/                   # settings, urls, wsgi
    core/                     # shared models, auth, reference data
    records/                  # Person A
      models.py  services.py  serializers.py  views.py  tests/
    planting/                 # Person B
      models.py  services.py  rules/  serializers.py  views.py  ussd.py  tests/
    seed/                     # seed_demo management command and fixtures
  frontend/
    src/
      api/  components/  pages/  i18n/
  docs/
```

---

## 9. Work split

| Area | Owner |
|---|---|
| `core/` models, auth, roles, OpenAPI skeleton | Both, on day 1 (about half a day) |
| `records/`: lots, events, hash chain, verification, loss calc | **Backend A** |
| `planting/`: advice rules, intents, slots, dashboard, USSD, data loading | **Backend B** |
| API client, screens, Swagger-driven types, Swahili/English labels | **Frontend** |
| Seed data and deployment | Backend B (seed), Backend A (deploy), reviewed together |

**Integration point:** the dashboard (6.4) needs stock from `records`. Backend A exposes `records.services.get_stock_by_ward(ward_id, crop)` returning `{stored_kg, avg_loss_pct, lot_count}`, and Backend B calls it. Agree on that signature on day 1.

**Git workflow**

- `main` is always deployable. Work on `feature/<name>` branches, small pull requests, one reviewer from the other side of the contract.
- Anyone changing an endpoint shape updates Section 6 in the same pull request.
- Run `python manage.py spectacular --file openapi.yaml` before merging API changes and commit the result.

---

## 10. Build order

| Phase | Backend A | Backend B | Frontend |
|---|---|---|---|
| 1. Foundation | Shared models, auth, seed users | Shared models, wards and crops, OpenAPI | Project setup, API client, login, mock server |
| 2. Core flows | Lot register, events, verify endpoints | Advice endpoint, intents, slot allocator | Register lot, lot detail, verify page, advice screen |
| 3. Integration | Stock service, hash chain check | Dashboard endpoint | Dashboard, intent screen |
| 4. Demo polish | Deploy, error handling | USSD simulator, seed script | Mobile polish, Swahili labels, empty states |

---

## 11. Demo data and shortcuts

- `python manage.py seed_demo` creates: 1 ward, 30 farmers, 2 agents, 1 cooperative admin, about 15 lots with realistic events (including one disputed lot), rainfall for one ward from a CHIRPS CSV, and a few price points.
- Demo logins: `agent@demo` / `coop@demo` / `farmer@demo`, all with the password `demo1234` (demo only, never in production).
- Rules engine is a plain Python function reading `planting/rules/v1.json`. No ML.
- Rainfall and prices come from files for the demo. Live ingestion is a later phase.
- Hardware sensors, payments, loans and watermelon storage are out of scope.

---

## 12. Security, privacy and quality baseline

- Consent is required before any farmer record is created (`consent_given` must be true).
- Farmer records are private by default. Each role sees only its tenant's data (filter every queryset by tenant).
- Public endpoints (`/verify/*`, `/ussd/`) are rate limited.
- Secrets live in environment variables: `SECRET_KEY`, `DATABASE_URL`, `CORS_ALLOWED_ORIGINS`, `AT_USERNAME`, `AT_API_KEY`. Never commit them.
- Tests to write at minimum: loss calculation, append-only enforcement, hash chain validity, oversubscription logic, tenant isolation, verify token expiry.

---

## 13. Open decisions

| Question | Needed by |
|---|---|
| Final pilot ward and county (seed data and rules depend on it) | Phase 2 |
| Real demand figures per ward and crop (`DemandEstimate`) | Phase 3 |
| Confirm Django (versus FastAPI or Node) with the whole team | Day 1 |
| Whether farmers log in to the web app or only use the verify link and USSD | Phase 1 |
| Where the demo will be presented (online or offline, affects hosting choice) | Phase 4 |
| Keep the HTML frontend and retire the React shell, or the reverse | Now |
| Loss method: raw weight difference (current) or dry-matter basis at a standard moisture | Before pilot |
| Whether signed-in farmers can list their own lots (needs a farmer-scoped endpoint) | Phase 2 |
