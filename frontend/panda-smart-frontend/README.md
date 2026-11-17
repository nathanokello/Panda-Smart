# Panda Smart Frontend

React 18 + Vite + TypeScript + Tailwind starter aligned to the backend architecture contract supplied by the team.

## Backend contract

- Django 5 + Django REST Framework
- PostgreSQL (SQLite may be used locally by backend)
- API root: `/api/v1/`
- Token auth: `Authorization: Token <key>`
- JSON uses `snake_case`; IDs are UUID strings.
- API errors use `{ "error": { "code", "message", "fields" } }`.
- Local backend default: `http://localhost:8000`.

This frontend intentionally does **not** use Supabase. It follows the uploaded backend README.

## Run

```bash
npm install
Copy-Item .env.example .env
npm run dev
```

Open http://localhost:5173. Vite proxies `/api/*` to `VITE_BACKEND_URL`.

## Demo mode

The default is real API mode (`VITE_USE_MOCKS=false`). When backend endpoints are still being developed, set `VITE_USE_MOCKS=true` in `.env` to allow sample data for read-only screens and a demo login. Sample data is not saved to the backend and must never be presented as live farmer records. Disable demo mode for integration testing and production.

Demo login accepts the seeded backend demo credentials only if the backend is running; with mock mode enabled it uses a local demonstration identity. Never deploy mock mode or demo credentials to production.

## Implemented API paths

- `POST /api/v1/auth/login/`
- `GET /api/v1/auth/me/`
- `GET /api/v1/wards/`
- `GET /api/v1/crops/`
- `GET, POST /api/v1/farmers/`
- `GET, POST /api/v1/lots/`
- `GET /api/v1/advice/?ward=<uuid>&crop=<code>`
- `POST /api/v1/planting-intents/`
- `GET /api/v1/dashboard/wards/`
- Public `GET /api/v1/verify/<token>/`, `POST .../confirm/`, `POST .../dispute/`

The API client sends token auth, parses the agreed error envelope and keeps the backend URL out of page components.

## Screens

- Login
- Overview
- Planting advice
- Planting slot / intent registration
- Hifadhi Mavuno lot list
- Farmer list
- Cooperative ward dashboard
- Public mobile-first verification route `/verify/:token`

The current prototype is intentionally a thin slice of the agreed backend scope. It does not invent endpoints for unsupported features. Add lot registration/event timeline and farmer registration when the matching backend endpoints are confirmed.

## Brand

The supplied Panda Smart logo is in `public/panda-smart-logo.png`. Brand colors use Deep Forest `#0E3A1E`, Sprout `#599827`, Fresh Lime `#8AC43E`, Emerald `#24692C`, Soft Mist `#F5F8F4`, Sage Border `#DCE6D9`.

## Important contract alignment notes

- API paths include trailing slashes.
- All request/response field names follow the backend's `snake_case` convention.
- Crops use `green_gram` and `cowpea` (not `ndengu` or `cowpeas` as API codes).
- Units: weight kg, area acres, moisture percent.
- Public verification does not require a login; all other protected calls attach `Authorization: Token ...`.
- Public verification responses should expose only the single authorized lot and its history.

## Integration with the Django backend

This app is wired to the backend at `C:\CLAUDE CODER\backend` (see its README).

- `npm install` then `npm run dev` starts the app on `http://localhost:5173` and
  proxies `/api/*` to `http://localhost:8000`. Start the Django server first:
  `..\..\backend\.venv\Scripts\python.exe ..\..\backend\manage.py runserver`.
- Leave `VITE_API_BASE_URL` empty in development so requests use the Vite proxy;
  set `VITE_USE_MOCKS=false` for real data.
- `src/api/client.ts` unwraps DRF pagination (`{ count, results }`) for wards and
  crops because those pages consume plain arrays.
- The ward dashboard combines `GET /dashboard/wards/` (ward summaries) with
  `GET /dashboard/wards/{id}/` (per-crop detail) to produce its table, matching
  `architecture.md` section 6.4.
- Backend verification links point at `http://localhost:5173/verify/<token>` by
  default (`FRONTEND_BASE_URL`), so the public verify route works locally.
- `src/vite-env.d.ts` and `@types/node` were added so `npm run build` type-checks
  cleanly.
