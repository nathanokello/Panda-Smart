# Panda Smart — HTML/CSS/JavaScript frontend

Plain HTML, CSS and JavaScript. No build step, no React. It talks to the Django
backend in `../../backend` using the contract in `../../architecture.md`.

## Run it (Windows, PowerShell)

Two terminals.

**Terminal 1: backend** (from the repo root)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8000
```

**Terminal 2: frontend** (from the repo root)

```powershell
cd frontend\html
python -m http.server 5500 --bind 127.0.0.1
```

Open <http://127.0.0.1:5500/login.html>. Use `127.0.0.1`, not `localhost`, for
both, or the browser treats them as different sites. Don't open the HTML files
by double-clicking (`file://`): the API calls are blocked.

Demo logins (password `demo1234`, demo data only):

| Phone | Role |
|---|---|
| +254700000001 | Storage agent |
| +254700000003 | Cooperative admin |
| +254700000004 | Administrator |
| +254700000005 | Farmer |

Run all commands from inside the extracted repo folder. Sign-ins last 7 days.

## Pages

| Page | Who | What it does | Endpoints |
|---|---|---|---|
| `login.html` | everyone | Phone + password sign-in | `POST /auth/login/` |
| `register.html` | farmers | Self-registration with consent | `POST /auth/register/farmer/`, `GET /wards/` |
| `index.html` | everyone | Role-aware dashboard, real figures only; farmers also see a 7-day forecast when the backend has it switched on | `/auth/me/`, `/farmers/`, `/lots/`, `/planting-intents/`, `/wards/{id}/weather/` |
| `farm.html` | farmer; staff with `?farmer=<id>` | Farmer record, plots, add plot; staff also see the farmer's lots | `/farmers/{id}/`, `/farmers/{id}/plots/`, `/lots/?farmer=` |
| `seasons.html` | farmer; staff with `?farmer=<id>` | What worked before (yield per acre, best season, storage loss), season records with harvest added later, soil tests with guidance | `/farmers/{id}/seasons/`, `/seasons/{id}/`, `/farmers/{id}/soil-tests/`, `/farmers/{id}/history/` |
| `farmers.html` | agent, coop admin, admin | List, search and register farmers | `GET, POST /farmers/` |
| `lots.html` | staff (register: agent, admin) | Lot list with filters; register a lot | `GET, POST /lots/` |
| `lot.html?id=` | staff (add records: agent, admin) | Loss with its formula, read-only history, add readings and corrections, integrity check, farmer link | `/lots/{id}/`, `/lots/{id}/events/`, `/lots/{id}/verify-chain/` |
| `verify.html?token=` | farmer, **no sign-in** | Confirm or dispute one lot; English/Kiswahili | `/verify/{token}/`, `/confirm/`, `/dispute/` |
| `advice.html` | everyone | Rule-based planting advice, planting windows, planting plans | `/advice/`, `/wards/{id}/slots/`, `/planting-intents/` |
| `wards.html` | coop admin, admin | Ward dashboard with privacy suppression | `/dashboard/wards/`, `/dashboard/wards/{id}/` |
| `users.html` | coop admin, admin | Staff accounts: create, rename, change role or cooperative (admins), reset password, deactivate/reactivate | `/users/`, `/users/{id}/`, `/tenants/` |
| `privacy.html` | everyone | Plain-language privacy notice (items to confirm are marked) | — |

## Files

- `js/config.js`: API address and every endpoint path.
- `js/api.js`: the only place that calls `fetch`. Adds the token, reads the
  `{"error": {...}}` envelope, follows paging, and sends you to sign-in on a 401.
- `js/ui.js`: sign-in check, role-based menu, formatting helpers.
- One script per page (`dashboard.js`, `farmers.js`, `farm.js`, `lots.js`,
  `lot.js`, `verify.js`, `advice.js`, `wards.js`, `privacy.js`, `auth.js`).
- `css/styles.css`: all styling.

The menu shows only pages that work for the signed-in role. The backend still
checks every permission; hiding a button is not security.

## Rules the pages keep

- No sample or invented data. Empty states say what is missing.
- Lot history is read-only. Mistakes are fixed with a correction entry.
- The loss figure is always shown with its formula.
- The verify page sends no sign-in token, so a stale token can't break it.

## Not built yet

- Farmers can't list their own lots after signing in (they use the private link).
- SMS sending of the verify link (Africa's Talking), USSD screens, offline entry.
- Full Kiswahili for the staff pages (the verify page has both languages; crop
  names show in both everywhere). Kiswahili text needs a native speaker's check.
