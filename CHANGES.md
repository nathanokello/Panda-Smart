# Changes in this update

## Navigation and marketplace
- Hifadhi Mavuno is now visible to signed-in farmers and staff in the HTML and
  React navigation.
- Farmers can list their own lots through Hifadhi Mavuno and browse only their
  own lot records.
- Added a working produce marketplace: farmers publish crop, quantity, price and
  optional lot details; marketplace listings are publicly readable without a
  sign-in.
- Added `ProduceListing` migrations and `/api/v1/marketplace/` API endpoints.

## Hifadhi Mavuno v10 integration
- Added Hifadhi v10 follow-up fields and scheduled 14/30/60-day storage checks.
- Moisture readings now produce dry, re-test or extension-officer decisions for
  maize using the configured 13.0% placeholder limit.
- Lot summaries expose both the existing plain-weight loss and a separate
  dry-matter-adjusted estimate.
- Added append-only system decisions to the lot history.
- Local database migrations: `records.0002_hifadhi_v10_followups` and
  `records.0003_alter_lotevent_type`.
- Verified with the full Django suite: 73 tests passing.

## Backend (Django)
- `planting/services.py` — added `get_ward_weather(ward)` (shared, cached weather
  lookup) and `get_farmer_dashboard(user)` (the data behind the new dashboard).
- `planting/views.py` — added `MyDashboardView`; `WardWeatherView` now calls the
  shared service instead of duplicating the caching logic.
- `planting/urls.py` — new route: `GET /api/v1/dashboard/me/`.
- `records/services.py` — added `get_lots_for_farmer(farmer_id)`.
- `records/views.py` / `records/urls.py` — new route:
  `GET /api/v1/me/verification-links/` (farmer's own pending verification links,
  reusing the existing USSD helper).
- `.env` — created from `.env.example`, pointed at the React app
  (`FRONTEND_BASE_URL=http://localhost:5173`, `FRONTEND_VERIFY_PATH=/verify/`),
  and `OPEN_METEO_ENABLED=1` so the dashboard's weather card has real data
  (seeded wards already have lat/lng). Set it back to `0` if your machine has
  no outbound internet, or if you later need Open-Meteo's commercial terms.

**I could not run `pip install` or `python manage.py test` in the sandbox that
built this (no network access there) — please run your existing test command
to confirm nothing broke:**
```
python -m pip install -r requirements.txt
python manage.py test
```

## Frontend (React, frontend/panda-smart-frontend)
- `src/api/types.ts` / `src/api/client.ts` — added types and calls for
  `/dashboard/me/`, `/farmers/{id}/plots/`, `/farmers/{id}/seasons/`,
  `/farmers/{id}/history/`, and `/me/verification-links/`.
- `src/App.tsx` — rebuilt sidebar nav and top bar to match your mockup
  (icons, search box, notification bell, avatar). New pages: Dashboard
  (farmer home screen with live stats/weather/AI recommendation/recent
  activity), My Farms, My Crops, Crop Analytics. Marketplace, Storage,
  Settings and Profile are clearly-labelled placeholders — they don't have
  dedicated backend support yet.
- `src/index.css` — new styles for the above, plus responsive rules at the
  existing 850px/520px breakpoints.
- `.env` — copied from `.env.example` (defaults already match the Django
  dev server on port 8000).

**I could not run `npm install` or `npm run build` in the sandbox either —
please run:**
```
npm install
npm run dev
```
and fix anything the TypeScript compiler flags that I couldn't catch by eye.

## Still on the roadmap (not built)
- Marketplace (buying/selling produce)
- A farmer-facing Storage view (today, storage is agent-managed only, by design)
- Profile editing, Settings

---

# Round 4 (18 November 2026): pitch-alignment and bug review

Reviewed against `Panda_Smart_Project_Overview1.docx` (Draft v1, 17 Nov 2026).
Full findings: `REVIEW_2026-11-18.md`. **Nothing here has been run**: the review
sandbox had no network, so Django, DRF and the npm packages could not be
installed. Backend files were compile-checked and the rules-engine change was
run on its own; run `python manage.py test` and `npm run build` before relying on it.

## Backend fixes
| Bug | Fix | Files |
|---|---|---|
| An agent could POST a `VERIFIED` or `DISPUTED` event and confirm a lot on the farmer's behalf | Events API accepts readings, check-ups, losses and corrections only | `records/serializers.py`, `records/services.py` |
| Staff or farmer accounts with no cooperative saw every farmer, lot and plan (filter on `tenant_id=None`) | Fail closed: no cooperative means no records | `core/services.py`, `records/services.py`, `planting/services.py` |
| Farmer's "Verification" page was empty for the demo farmer (login phone differs from farmer-record phone) | Links looked up by farmer id | `records/services.py`, `records/views.py` |
| Bad `corrects_event_id` and `nan`/`inf` readings caused a 500 | Validated | `records/services.py` |
| Two simultaneous writes could break the hash chain or double-record a farmer response | Row locks and transactions | `records/services.py` |
| Watermelon (out of scope for storage) could be registered as a lot through the API | Rejected | `records/serializers.py`, `records/services.py` |
| Planting window could start in the past (onset is always historical) | Window starts today at the earliest | `planting/rules/engine.py` |
| Ward dashboard compared every season's plans with this season's demand | Filtered to the season | `planting/services.py` |
| A plot of another farmer could be attached to a plan | Checked | `planting/services.py` |
| Network resets from the weather API gave a 500 on the farmer dashboard | Caught | `planting/weather.py` |
| Login throttle crashed on a non-object JSON body | Guarded | `core/authentication.py` |
| Re-running `seed_demo` left old rules in the database | Rules refreshed from `v1.json` | `seed/.../seed_demo.py` |
| Two tests failed with the shipped `.env` (verify link path, weather default) | Settings pinned in the tests | `records/tests.py`, `planting/tests.py` |
New regression tests: `SafeguardRegressionTests`, `ReviewRegressionTests`.

## React app fixes (`frontend/panda-smart-frontend`)
- Sign-out now revokes the token on the server; an expired token returns the user to sign-in.
- Lists follow pagination (before: only the first 20 wards, farmers or lots).
- Farmers can now register planting intents (before: staff only, and by typing two UUIDs).
- Verification page is readable and bilingual (before: raw JSON, English only), and cannot be submitted twice.
- Login no longer pre-fills a demo phone and password; "AI Crop Recommendation" relabelled "rule-based".
