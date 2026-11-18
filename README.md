# Panda Smart

## The problem

Smallholder maize farmers in Kenya make planting, storage and sale decisions
without reliable records of their soil, their past seasons, or the condition of
their grain. Because they can't see what worked before, they repeat the same
crops and methods, and they lose part of their harvest in storage. When they
sell, they often do it at harvest, when prices are lowest, and they have no
reliable proof of their grain's quality, so disputes over moisture and weight
go against them. The result is that farmers lose both grain and income at every
stage, and they have no simple way to learn from one season to the next.

## How Panda Smart answers it

| Part of the problem | What Panda Smart does | Status |
|---|---|---|
| No record of past seasons; repeating crops and methods by habit | Season records (crop, variety, methods, harvest) and a "what worked before" summary: yield per acre per crop, best season and how it was grown | Built |
| No record of soil | Soil test entry (lab, kit or extension officer) with simple guidance that always points to an extension officer | Built (manual entry; soil maps planned) |
| Planting decisions without data | Rule-based planting window from rainfall records (NASA POWER), optional forecast, ward planting plans that flag oversubscribed crops | Built |
| Grain lost in storage | Lot records with moisture and weight readings, loss shown with its formula; loss per crop feeds the season summary | Built |
| No proof of quality at sale; disputes go against farmers | Append-only, hash-chained lot history; farmer confirms or disputes through a private link; agents can share the record | Built |
| Selling at harvest when prices are lowest | Ward dashboard selling flag from recent prices (demo prices); stored grain record supports holding and selling later | Partly built (live prices planned) |
| No simple way to learn season to season | Season summary combines yield, methods and storage loss per crop | Built (season close-out prompts planned) |

## About

A farmer platform for Kenyan smallholders. The first module, **Hifadhi Mavuno**,
is a grain storage proof record: a dated, tamper-evident history of each stored
lot's weight and moisture, which the farmer confirms or disputes through a
private link and can show at sale. Planting advice and ward planning sit
alongside it.

> Status: working prototype for demos and a small pilot. Not yet tested with
> real farmers. Every claim below says whether it is **built**, **partly
> built** or **planned**.

## What it does

| Area | What users can do | Status |
|---|---|---|
| Accounts | Farmers register themselves (phone + password, consent required). Admins and coop admins create staff accounts on the Users page. Sign-in tokens expire after 7 days; sign-out revokes them | Built |
| Farmers and plots | Agents register farmers (with consent) and plots (approximate size only, no GPS) | Built |
| Season history | Farmers or agents record each season's crop, variety, methods and harvest; summary shows average and best yield per acre and storage loss per crop | Built |
| Soil records | Enter soil test results; general guidance on pH and organic matter, with "confirm with an extension officer" | Built (manual entry) |
| Hifadhi Mavuno | Agents register grain lots and add moisture, weight, check-up and loss records. History is append-only and hash-chained; mistakes are fixed with correction entries | Built |
| Loss figure | Plain weight difference, shown with its formula, corrections applied | Built (method still to agree, see open decisions) |
| Farmer verification | Private link, no login, English/Kiswahili: confirm or dispute once; expires in 14 days | Built |
| Planting advice | Rule-based planting window from rainfall records, with a confidence score | Built (rules, not AI) |
| Rainfall data | `fetch_rainfall` pulls daily rainfall from NASA POWER into the advice rules | Built, untested against the live API from this workspace |
| Weather forecast | 7-day forecast panel on the farmer dashboard (Open-Meteo) | Built, **off by default** (non-commercial licence) |
| Planting plans | Farmers or agents record intended crop and acres; oversubscribed crops are moved to a later window | Built |
| Ward dashboard | Planned acres vs demand, stored stock, loss, price-based selling flag; crops with fewer than 5 farmers hidden | Built (demo prices) |
| USSD | Menus for advice, planting slot and verify link (Africa's Talking simulator) | Built, simulator only |
| SMS sending of links and reminders | — | Planned |
| Soil maps (iSDAsoil), crop matching, AI explanations, translation, voice | — | Planned (see `docs/data-sources.md`) |
| Offline entry for agents | — | Planned |
| Scheduled 14/30/60-day checks, buyer role | — | Not started (team decision) |
| Payments | — | Out of scope: Panda Smart never holds or moves money |

## Who sees what

The backend enforces every rule below; the web app only hides what a role can't use.

| | Farmer | Storage agent | Coop admin | Administrator |
|---|---|---|---|---|
| Own farm, plots, planting plans, seasons, soil tests | ✓ | | | |
| Seasons and soil tests of farmers in own cooperative | | ✓ | ✓ | all |
| Farmers in own cooperative | | ✓ | ✓ | all |
| Register farmers | | ✓ | ✓ | ✓ |
| View lots (own cooperative) | | ✓ | ✓ | all |
| Register lots, add records | | ✓ | | ✓ |
| Ward dashboard | | | ✓ | ✓ |
| Manage staff accounts | | | agents in own cooperative | all staff |
| Confirm/dispute a lot | via private link | | | |

Nobody can change their own role or status. Accounts are deactivated, never deleted.

## Repository layout

```
architecture.md          Shared API contract (read before changing an endpoint)
INTEGRATION_NOTES.md     What changed in the HTML frontend integration, and why
openapi.yaml             Generated API schema (regenerate after API changes)
docs/data-sources.md     Weather, soil, crop and language sources: checked status and licences
backend/                 Django 5 + Django REST Framework
  core/                  Users, roles, cooperatives, wards, crops, farmers, plots, auth
  records/               Lots, append-only events, hash chain, loss, verify links
  planting/              Advice rules, planting plans, slots, dashboard, USSD, weather
  seed/                  seed_demo command and demo data files
frontend/html/           The web app: plain HTML, CSS and JavaScript (no build step)
frontend/panda-smart-frontend/   Unfinished React shell (team to decide: keep or remove)
```

## Run it locally (Windows, PowerShell)

You need Python 3.10 or newer (Django 5.2 requires it). Open the repo folder in VS Code, then two terminals.

**Terminal 1: backend**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py test
python manage.py runserver 127.0.0.1:8000
```

If PowerShell refuses to run `Activate.ps1`, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again.
Make sure you are inside the extracted folder (the one that contains `backend`
and `frontend`) before running these commands.

**Terminal 2: web app**

```powershell
cd frontend\html
python -m http.server 5500 --bind 127.0.0.1
```

Open <http://127.0.0.1:5500/login.html>. Use `127.0.0.1` for both servers.

**Demo logins** (password `demo1234`, demo data only, never in production):

| Phone | Role |
|---|---|
| +254700000001 | Storage agent |
| +254700000003 | Cooperative admin |
| +254700000004 | Administrator |
| +254700000005 | Farmer |

**Optional: real rainfall and a forecast**

```powershell
python manage.py fetch_rainfall --days 60        # NASA POWER, free, no key
$env:OPEN_METEO_ENABLED = "1"                     # demo only: non-commercial licence
python manage.py runserver 127.0.0.1:8000
```

API docs while the server runs: <http://127.0.0.1:8000/api/docs/>

## Settings

All settings are environment variables (or `backend/.env`). See
`backend/.env.example` and `backend/README.md` for the full list. The important ones:

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | dev value | Must be set to a long random value outside your laptop |
| `DEBUG` | `1` | Set `0` in any shared or public deployment |
| `CORS_ALLOWED_ORIGINS` | 127.0.0.1:5500 and others | Where the web app is served from |
| `FRONTEND_BASE_URL`, `FRONTEND_VERIFY_PATH` | `http://127.0.0.1:5500`, `/verify.html?token=` | Builds farmer verify links |
| `TOKEN_TTL_HOURS` | `168` | Sign-in lifetime |
| `USSD_CALLBACK_SECRET` | empty | Required when `DEBUG=0`; put `?key=<secret>` in the Africa's Talking callback URL |
| `OPEN_METEO_ENABLED` | `0` | Forecast panel; free tier is non-commercial only |
| `RAINFALL_SOURCE_PRIORITY` | `NASA_POWER,CHIRPS` | Which rainfall source the advice uses |

Never commit `.env`, real farmer data or database files.

## Rules the code keeps

- No record about a farmer is created without consent.
- Lot history is never edited or deleted. Corrections are new entries, and a
  SHA-256 hash chain lets anyone check nothing was changed.
- Every role sees only its own cooperative's farmers and lots.
- Dashboards hide any crop with fewer than 5 farmers in a ward.
- Voice is never used to identify people (Kenya Data Protection Act, 2019).
- Panda Smart does not hold or move money.

## Open decisions

1. Keep the HTML web app and remove the React shell?
2. Loss method: plain weight difference (current) or dry-matter at a standard moisture?
3. Scheduled 14/30/60-day checks and a buyer role?
4. Let signed-in farmers list their own lots (needs a farmer-only endpoint)?
5. Issuing a new verify link after the first is used or expires.
6. Should coop admins also create other coop admins? (Currently admins only;
   one line in `core/services.py`, `MANAGEABLE_ROLES`.)
7. Weather and translation licences for commercial use (see `docs/data-sources.md`).
8. Privacy notice items marked `[to confirm]` in `frontend/html/privacy.html`.

## Known limits

- The Django tests were written alongside the code but must be run on your
  machine (`python manage.py test`) before you rely on them.
- Phone numbers are normalised but not verified (needs SMS codes).
- Login limits use Django's cache; with several server processes, use a shared cache.
- Kiswahili text needs a native speaker's check.
