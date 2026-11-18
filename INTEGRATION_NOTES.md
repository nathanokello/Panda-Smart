# HTML frontend integration: what changed and why

Date: 18 November 2026. Scope: connect the plain HTML/CSS/JS frontend to the
team's Django backend, fix the bugs found on the way, and add the missing screens.

## 1. Read this first: the project brief and this repo don't match

The brief I was given describes a **different backend** from the one in this repo.
Before using the brief in a pitch or document, align it with what this repo does:

| Brief says | This repo actually does |
|---|---|
| Roles: farmer, storage agent, **buyer**, administrator | Roles: `farmer`, `agent`, `coop_admin`, `admin`. **No buyer role.** Buyers exist only as a tenant type |
| Checks at **14, 30 and 60 days**, one completion each | **No scheduled checks.** Agents add readings and check-ups whenever they like |
| Loss on a **dry-matter basis at 13.0%** (1000 kg at 14% → 900 kg at 13% = 88.51 kg) | Loss = **plain weight difference** (same example gives 100 kg). Drying counts as loss |
| Harvest and farm entry | Farmer + plots. **No harvest record** |
| Planting advice **planned** | Planting advice, slots, intents and a ward dashboard are **built** (rule-based, demo rainfall and price files) |
| Farmers must log in to respond | Farmers respond through a **private link, no login** (built) |
| Phone lookup endpoint lets agents find farmers | Not in this repo |
| Audit trail | Built differently: a **SHA-256 hash chain** over lot events, with an integrity check |

My view: the hash chain and the private verify link are stronger than what the
brief describes, so keep them. The dry-matter loss method is the bigger open
question (Section 5). I did **not** change the loss method, because the
architecture calls it the "single definition, used everywhere" and changing it
is a team decision.

## 2. Backend changes

Status: written and compile-checked. **The Django test suite has not been run**:
this workspace has no internet, so Django could not be installed. Run
`python manage.py test` before you rely on these changes.

| Change | Why | Files |
|---|---|---|
| Farmer self-registration `POST /auth/register/farmer/` (role forced to farmer, consent required, rate limited) | `register.html` needed it; it didn't exist | `core/views.py`, `core/serializers.py`, `core/services.py`, `core/urls.py`, `config/settings.py` |
| `/auth/me/` returns `farmer_id` | A signed-in farmer needs it to load their own record and plots | `core/serializers.py` |
| Phone numbers normalised to `+2547…` at login and registration | `0712 345 678` and `+254712345678` could become two accounts; login failed if typed differently | `core/phone.py` (new), `core/serializers.py` |
| `POST /auth/logout/` deletes the token | Tokens never stopped working after sign-out (one of your listed security concerns) | `core/views.py`, `core/urls.py` |
| Wards, crops and the verify endpoints skip token authentication | A stale token in the browser caused a 401 on public pages | `core/views.py`, `records/views.py` |
| Verify links point at `verify.html?token=` (configurable) | They pointed at a React route that doesn't exist | `records/services.py`, `config/settings.py` |
| Corrections are applied to the loss figure; corrected values are validated | A `CORRECTION` was stored but ignored, so a typo stayed in the loss forever | `records/services.py`, `records/serializers.py` |
| `oversubscription_pct` = share **above** demand | Code returned 133.33 where the contract example says 33.3 | `planting/services.py` |
| Farmers can list their own planting intents | The query already limited farmers to their own, but the role check blocked them | `planting/views.py` |
| Advice schema shows `{start, end}` | The OpenAPI schema described the window as a slot, so generated docs were wrong | `planting/serializers.py` |
| `.env.example` fixed | Copying it would have blocked the HTML frontend (CORS) and used a database path from one teammate's PC | `backend/.env.example` |
| Tests for all of the above | So you can confirm on your machine | `core/tests.py`, `records/tests.py`, `planting/tests.py` |

After the tests pass, regenerate the schema:
`python manage.py spectacular --file ../openapi.yaml`

## 3. Frontend changes (`frontend/html/`)

Tested in a headless browser against a stand-in API with the same response
shapes as the serializers: 39 checks across all four roles, desktop and phone
widths, all passing. That proves the pages work with those shapes, **not** that
they work with your running Django. Test against the real backend before demo day.

- **Fixed:** error messages showed `[object Object]` (the backend wraps errors
  in `{"error": {...}}`); paged lists only read the first 20 records; the ward
  list showed names without county; a revoked token left the user stuck; sign-out
  didn't revoke the token; menu items opened "coming soon" pop-ups; the
  dashboard showed weather and "AI recommendation" panels with no backend
  behind them (removed; the advice is rule-based, so it is labelled that way).
- **Added pages:** farmers, farm/plots, lots, lot detail, public verify page
  (English/Kiswahili), planting advice and plans, ward dashboard, privacy notice.
  See `frontend/html/README.md` for the page-by-page table.
- **Kept:** the original look, colours, logo and images.
- The React folder `frontend/panda-smart-frontend/` is **untouched**. It is an
  unfinished shell (about 100 lines). The team should decide to remove it or not.

## 4. Security concerns from the brief: status

| Concern | Status |
|---|---|
| Phone numbers not verified at registration | **Still open.** Normalised, not verified. Needs an SMS code (Africa's Talking) |
| Tokens never expire; logout doesn't revoke | **Logout now revokes.** Expiry still open (suggest a 7–30 day lifetime) |
| Phone lookup endpoint | Not in this repo |
| Login throttled per IP only | **Still open.** Add a per-phone limit before the pilot |
| New: wards and crops are public | Intended (the sign-up form needs them). They hold no personal data |
| New: the ward dashboard shows all wards to every coop admin | Totals only, with fewer-than-5 suppression; confirm that's acceptable |

## 5. Open decisions (team)

1. Keep the HTML frontend and remove the React shell?
2. Loss method: plain weight difference (current) or dry-matter at a standard
   moisture (brief)? If dry-matter, add it as extra fields so the contract stays stable.
3. Add scheduled checks (14/30/60 days) and a buyer role, as the brief describes?
4. Should signed-in farmers see their own lots? This needs a farmer-scoped endpoint;
   the current lot list would show a farmer their whole cooperative's lots.
5. A way to issue a new verify link after the first is used or expires.
6. Privacy notice items marked `[to confirm]`: sharing, retention, contact, data controller.
7. A native speaker to check the Kiswahili on the verify page.

---

# Round 2 (18 November 2026): user management, bug sweep, weather

Same caveat: compile-checked and browser-tested against a stand-in API (all
checks passing), but **run `python manage.py test` on your machine**.

## Added

| What | Files |
|---|---|
| Staff user management: admins manage all staff; coop admins manage agents in their own cooperative. No deletes, no self-edits, tokens revoked on role, password or status change. `GET/POST /users/`, `GET/PATCH /users/{id}/`, `GET /tenants/` | `core/services.py`, `core/serializers.py`, `core/views.py`, `core/urls.py`, `frontend/html/users.html`, `js/users.js` |
| Sign-in tokens expire (default 7 days); login limited per phone number as well as per IP; last sign-in recorded | `core/authentication.py` (new), `core/views.py`, `config/settings.py` |
| NASA POWER rainfall: `fetch_rainfall` command feeds the advice rules | `planting/weather.py` (new), `planting/management/commands/fetch_rainfall.py` (new) |
| Optional 7-day forecast (Open-Meteo, off by default because the free tier is non-commercial) | `planting/views.py`, `planting/urls.py`, `frontend/html/js/dashboard.js` |
| Complete root README; data-sources guide with checked licences | `README.md`, `docs/data-sources.md` |

## Bugs fixed

| Bug | Effect | Fix |
|---|---|---|
| Public USSD endpoint returned a farmer's private verify link for any phone number sent to it | Anyone could confirm or dispute another farmer's lot | Shared secret in the callback URL; required when `DEBUG=0` (`planting/views.py`) |
| USSD looked up `0712…` and `+254712…` as different people | "My planting slot" failed for local-format numbers | Phone normalised (`planting/ussd.py`) |
| USSD replies could exceed one screen; session state could exceed its 50-character column | Cut-off text; database error on PostgreSQL | Replies capped at 182 characters; state trimmed |
| Advice added rainfall from every source | Importing NASA data beside the demo CSV would count rain twice and trigger planting early | One source per ward, in priority order (`planting/services.py`) |
| Advice text said "onset expected in the last week of November" whatever the data showed, and called a today+12 placeholder a "seasonal typical window" | Misleading advice | Rationale now states the recorded onset date, or says plainly it is a placeholder (`planting/rules/`) |
| Seed coordinates: Westlands about 23 km north of Nairobi; "Makueni Town" about 38 km west of Wote | Wrong weather for those wards | Corrected; re-running `seed_demo` updates existing wards |
| Weak passwords crashed the server (500) when staff accounts or farmer logins were created | Server error instead of a message | Converted to a 400 with the reasons; agent-created farmer logins now checked too |
| `import_rainfall` matched wards by name only | Rows could go to the wrong county | Optional `county` column; ambiguous rows skipped with a message |
| New test classes re-ran the original tests | Slower suite, confusing counts | Shared fixtures split out |

## Your list of security concerns: now

| Concern | Status |
|---|---|
| Tokens never expire / logout doesn't revoke | **Fixed** (7-day expiry, revoke on sign-out and on account changes) |
| Login throttled per IP only | **Fixed** (also per phone; use a shared cache with several server processes) |
| Phone numbers not verified | Open: needs SMS codes |
| Open USSD endpoint | **Fixed** (see above) |

---

# Round 3 (18 November 2026): seasons and soil, to cover the full problem

The problem statement includes "no reliable records of their soil, their past
seasons… no simple way to learn from one season to the next". The system had
nothing for that. Added:

| What | Files |
|---|---|
| `SeasonRecord` and `SoilTest` models with a hand-written migration (`0002`). Run `python manage.py makemigrations --check`; if it reports changes, generate the migration with `makemigrations planting` instead | `planting/models.py`, `planting/migrations/0002_seasonrecord_soiltest.py` |
| Season, soil and history endpoints; "what worked before" summary including storage loss per crop from Hifadhi Mavuno | `planting/history.py` (new), `planting/serializers.py`, `planting/views.py`, `planting/urls.py`, `records/services.py` |
| Soil guidance rules (pH below 5.5, above 7.5, organic carbon below 1%), always ending with "confirm with an extension officer" | `planting/history.py` |
| `seasons.html` page; links from the farmer dashboard and farm page | `frontend/html/seasons.html`, `js/seasons.js`, `js/dashboard.js`, `js/farm.js`, `js/ui.js` |
| Tests: season records, harvest added later, date checks, privacy between farmers, soil guidance, storage loss in history | `planting/tests.py` |

Frontend fixes found while testing: the `hidden` attribute was overridden by
button styles (a "Cancel" button stayed visible); the soil-test date defaulted
to yesterday late at night because it used UTC.
