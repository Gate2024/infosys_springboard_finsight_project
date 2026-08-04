# Expense Integration Report

Analyzed only. No files were modified during the analysis phase.

Main project: `D:\FinSight`, branch `milestone-2-ui-revamp`  
Expense module: `D:\FinSight\expense-module`, branch `expenseee-tracking`

The main app should remain the integration host. The expense module is useful mainly as source material for transaction schema, expense UI behavior, analytics ideas, and dependencies. It should not be copied wholesale because its Flask app duplicates auth routes, uses different session keys, has different user column names, and its real expense dashboard is Streamlit, not Flask/Jinja.

## High-Level Verdict

| Area | Finding | Integration Decision |
|---|---|---|
| Flask routes | Main app owns `/`, `/login`, `/register`, `/logout`, `/dashboard`, `/budget`, budget CRUD. Expense module duplicates only auth/dashboard routes. | MERGE expense routes into main `app.py`, do not copy module `app.py`. |
| Blueprints | Main has `backend/auth.py` blueprint but not registered. Expense module has no blueprint. | IGNORE old blueprint unless refactoring later. |
| `app.py` | Main `app.py` is current canonical Flask controller. Expense `app.py` is a small standalone auth demo. | KEEP main, IGNORE expense `app.py`. |
| `db.py` | Main `db.py` supports users and budgets using `Config`. Expense `db.py` supports users and `transactions` using `SUPABASE_DB_URI` and bcrypt. | MERGE transaction DB functions/schema into main `db.py`. |
| Authentication | Main uses email login, `werkzeug.security`, `password_hash`. Expense uses username login and bcrypt column `pwd`. | KEEP main auth. Do not replace it. |
| Session usage | Main uses `uid`, `username`, `email`. Expense Flask uses `uid`, `name`; Streamlit uses its own `st.session_state`. | Standardize on main Flask session keys. |
| Database schema | Main has `users` + `budgets`. Expense has `users` + `transactions`. User table conflicts. | MERGE only `transactions` table into main schema. |
| Expense CRUD | Expense CRUD exists only in Streamlit `src/views/dashboard.py`, not Flask. | MERGE behavior into new Flask/Jinja routes later. |
| Templates | Main templates are much more complete. Expense Flask templates are placeholder auth pages. | KEEP main templates; MERGE only expense dashboard ideas. |
| CSS | Main CSS is already adapted for Flask. Expense frontend CSS is older auth-card styling. Streamlit CSS cannot be copied directly. | KEEP main CSS; selectively MERGE expense-dashboard styling if porting. |
| JavaScript | Main auth JS submits forms correctly. Expense frontend JS blocks real submits. | KEEP main JS; IGNORE expense auth JS. |
| Static assets | No real image/assets found, only CSS/JS and CDN dependencies. | KEEP main static structure. |
| Sidebar navigation | Main has two sidebar systems: `base.html` budget sidebar and `main_dashboard.html` full dashboard sidebar. Expense Streamlit sidebar has richer nav labels. | MERGE nav label/route intent, not code. |
| Duplicate files | `database/db.sql` files are both empty and identical. Several same-name files differ semantically. | IGNORE empty/placeholder duplicates. |
| Dependencies | Main requirements miss expense dependencies: bcrypt, streamlit, pandas, plotly. For Flask integration, probably only bcrypt is optional, and Plotly/Pandas may not be needed if using JS charts. | MERGE only dependencies actually used by Flask implementation. |

## Route Comparison

Main canonical routes are in `app.py`.

| Route | Main Project | Expense Module | Classification |
|---|---|---|---|
| `/` | Redirects authenticated users to dashboard, otherwise login. | Same idea, standalone. | KEEP main |
| `/login` | GET/POST, email/password, hashed password check. | GET/POST, username/password via bcrypt. | KEEP main |
| `/register` | POST handled by combined login/register page; GET redirects to login. | GET/POST separate register page. | KEEP main, possibly MERGE separate register UX only if desired |
| `/logout` | Clears Flask session. | Clears Flask session. | KEEP main |
| `/dashboard` | Renders `main_dashboard.html` with summary stats. | Placeholder dashboard. | KEEP main |
| `/expense` | Exists, but renders `expense.jsx`, which is not present. | No Flask expense route. | MERGE/REWORK needed |
| `/budget`, `/budgets` | Budget dashboard with filters. | No budget route. | KEEP main |
| `/budget/create` | Create budget. | No equivalent. | KEEP main |
| `/budget/edit/<id>` | Edit budget. | No equivalent. | KEEP main |
| `/budget/view/<id>` | JSON budget detail. | No equivalent. | KEEP main |
| `/budget/delete/<id>` | Delete budget. | No equivalent. | KEEP main |

Important gap: `app.py` defines `/expense`, but it tries to render `expense.jsx`; no such template exists. This route is a placeholder and cannot work as-is.

## Blueprints

| File | Classification | Why |
|---|---|---|
| `backend/auth.py` | IGNORE | Defines `auth = Blueprint(...)`, but it is not registered in main `app.py`. It also imports `conn, cursor` from `db`, which main `db.py` does not expose, and stores/checks plain passwords. |
| `expense-module` | IGNORE | No blueprint implementation found. |

## `app.py` Comparison

### Main `app.py`

Classification: KEEP

Why:

- It is the active Flask entrypoint for the main project.
- It already centralizes login, registration, logout, dashboard, and budget CRUD routes.
- It uses `Config.SECRET_KEY` instead of a hardcoded secret.
- It relies on main `db.py` helpers for auth and budget behavior.
- It enforces authenticated access through `login_required_redirect()`.
- It uses the main session model: `uid`, `username`, `email`.

Integration notes:

- The `/expense` route should not be considered complete because it renders `expense.jsx`, which is missing.
- New expense routes should be added into this file or, preferably later, into a properly registered blueprint if the project is refactored.
- Existing budget routes should be kept intact.

### Expense Module `app.py`

Classification: IGNORE

Why:

- It is a standalone Flask auth shell.
- It duplicates `/`, `/login`, `/register`, `/dashboard`, and `/logout`.
- It uses a hardcoded secret: `your-secret-key-here`.
- It logs in by username (`name`) and password (`pwd`), while the main app logs in by email and password.
- It stores session keys as `uid` and `name`, while the main app uses `uid`, `username`, and `email`.
- It does not implement expense CRUD routes.
- It would conflict with main app route names and endpoint names if copied directly.

## `db.py` Comparison

### Main `db.py`

Classification: MERGE

Why:

- Keep this as the canonical DB abstraction.
- It already provides connection handling through `Config`.
- It uses `RealDictCursor`, which works well with Jinja and JSON serialization.
- It provides safe parameterized queries.
- It already contains user auth helpers and budget CRUD helpers.

Existing main DB capabilities:

- `get_connection()`
- `register_user(username, email, password)`
- `login_user(email, password)`
- `create_budget(user_id, data)`
- `get_all_budgets(user_id)`
- `filter_budgets(...)`
- `get_budget(budget_id, user_id)`
- `update_budget(budget_id, user_id, data)`
- `delete_budget(budget_id, user_id)`
- `get_summary_stats(user_id)`

Integration notes:

- Add transaction helpers here later, using the same style as budget helpers.
- Expense helpers should use `user_id` scoping consistently.
- Expense helper return values should be serialized with the existing `serialize_row()` / `serialize_rows()` helpers.

### Expense Module `db.py`

Classification: MERGE

Why:

- It contains the useful transaction schema and auth hashing implementation.
- It should not replace main `db.py`.
- It uses a different env var (`SUPABASE_DB_URI`) and different user schema.
- Its transaction functions are incomplete for Flask integration because most CRUD behavior lives in the Streamlit dashboard file.

Useful pieces to merge conceptually:

- `transactions` table definition.
- `payment_mode` field.
- Auto-migration checks for `payment_mode` and `created_at`.
- Bcrypt hashing only if migrating existing expense-module users, not for the main auth path.

Do not merge directly:

- `users` table definition with `name` and `pwd`.
- `reg_user()` and `login_user()` names/behavior.
- Raw `SUPABASE_DB_URI`-only connection approach.

## Authentication And Session Flow

Main auth is the safer base:

- Login form posts `email` and `password`.
- Main `db.py` checks `users.email`.
- Passwords use Werkzeug `generate_password_hash` / `check_password_hash`.
- Session keys are `uid`, `username`, `email`.
- `session.clear()` is called before setting login session values.
- Authenticated pages use `session.get("uid")`.

Expense module auth differs:

- Expense Flask app logs in with `name` and `pwd`.
- Expense `db.py` stores bcrypt hashes in column `pwd`.
- Expense session keys are `uid` and `name`.
- Streamlit dashboard does not use Flask sessions at all.
- Streamlit dashboard hardcodes/defaults `user_id = 1` and `username = "Venkat"` in `st.session_state`.

Recommendation:

KEEP main auth/session model. MERGE expense records by using `session["uid"]` as `transactions.user_id`.

Do not introduce `session["name"]` or `session["user_id"]` unless the entire app is migrated consistently. The existing main app expects `uid`.

## Database Schema

Main schema is in `database/schema.sql`.

Main schema currently has:

- `users(id, username, email, password_hash, created_at)`
- `budgets(...)`
- indexes for budget lookups
- update trigger for budget `updated_at`

Expense module schema exists in code, not SQL, because `expense-module/database/db.sql` is empty.

Expense tables from `expense-module/db.py`:

- `users(id, name, email, pwd, created)`
- `transactions(id, user_id, amount, type, category, date, description, payment_mode, created_at)`

Classification:

| Schema Item | Classification | Why |
|---|---|---|
| Main `users` table | KEEP | Current app depends on `username`, `email`, `password_hash`. |
| Expense `users` table | IGNORE | Conflicts with main user schema and auth flow. |
| Main `budgets` table | KEEP | Existing budget module depends on it. |
| Expense `transactions` table | MERGE | This is the core expense data model. Add it to main schema using main `users(id)` FK. |
| Empty `database/db.sql` files | IGNORE | Both are zero-byte duplicates. |

Recommended future transaction schema direction:

- Use `transactions.user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE`.
- Keep `amount NUMERIC(12,2)` or `DECIMAL(10,2)`.
- Keep `type VARCHAR(20)` if income and expense will share the table.
- For expense-only routes, filter `type = 'Expense'`.
- Keep `category`, `date`, `description`, `payment_mode`, `created_at`.
- Consider adding `updated_at` for edit tracking.
- Add indexes on `user_id`, `type`, `category`, and `date`.

## Expense CRUD

The real expense CRUD is in `expense-module/src/views/dashboard.py`, but it is Streamlit.

| Operation | Location | Classification | Why |
|---|---|---|---|
| Create expense | `add_transaction(...)` | MERGE | Logic is useful, but must become Flask route + DB helper. |
| Read expense history | SQL around expense history query | MERGE | Useful query shape for current-month expense list. |
| Update expense | `update_transaction(...)` | MERGE | Needs `user_id` scoping before integrating. |
| Delete expense | `delete_transaction(...)` | MERGE | Needs `user_id` scoping before integrating. |
| Category auto-classification | `show_add_expense_dialog()` | MERGE | Good feature idea; port into Flask server helper or frontend JS. |
| Analytics/charts | Streamlit + Plotly code | MERGE CONCEPT ONLY | Cannot be copied directly into Flask templates. |

Security note:

The Streamlit delete/update queries use only transaction id:

- `DELETE FROM transactions WHERE id = %s`
- `UPDATE transactions SET ... WHERE id = %s`

Flask integration should require user scoping:

- `WHERE id = %s AND user_id = %s`

Functional behavior worth preserving:

- Add expense modal/dialog behavior.
- Category inference from description.
- Payment mode field.
- Current-month expense history.
- Expense summary metrics.
- Expense trend view with monthly/weekly mode.
- Category breakdown chart.
- CSV/export idea, if needed.

Functional behavior to revise:

- Do not hardcode `uid = 1`.
- Do not use Streamlit session state in Flask.
- Do not use MySQL-specific syntax like `YEARWEEK()` against PostgreSQL. The module has a query comment mismatch and some PostgreSQL/MySQL syntax mixing.
- Do not query all data directly inside the view layer once ported to Flask; use DB helper functions.

## Templates

| File | Classification | Why |
|---|---|---|
| `templates/login.html` | KEEP | Integrated with main Flask routes and form field names. |
| `templates/base.html` | KEEP | Canonical shell for budget pages. |
| `templates/main_dashboard.html` | MERGE | Current dashboard shell has full sidebar including Expenses link, but routes are partly placeholders. |
| `templates/dashboard.html` | KEEP | Main app's simple authenticated dashboard page. |
| `templates/budget_dashboard.html` | KEEP | Current budget listing UI. |
| `templates/budget_form.html` | KEEP | Current budget create/edit UI. |
| `expense-module/templates/login.html` | IGNORE | Plain placeholder, wrong field names for main auth. |
| `expense-module/templates/register.html` | IGNORE | Plain placeholder, wrong field names. |
| `expense-module/templates/dashboard.html` | IGNORE | Placeholder success page only. |
| `expense-module/frontend/login.html` | IGNORE | Static prototype; main login has already evolved from it. |
| `expense-module/src/views/dashboard.py` | MERGE CONCEPT ONLY | Large Streamlit dashboard, not a Flask template. |

Template integration recommendation:

- Create a future Flask/Jinja expense template that extends `base.html` or aligns with `main_dashboard.html`.
- Do not try to render `.jsx` from Flask unless a React build pipeline is introduced.
- Do not copy Streamlit markup/CSS directly; port the layout and behavior into HTML/Jinja.

## CSS

| File | Classification | Why |
|---|---|---|
| `static/css/style.css` | KEEP | Main auth styling; adapted to Flask login page. |
| `static/css/main_dashboard.css` | MERGE | Useful dashboard/sidebar styling, but should be reconciled with `base.html` shell. |
| `static/css/app.css` | KEEP | Main shared app shell/sidebar styling. |
| `static/css/budget.css` | KEEP | Budget dashboard styling. |
| `static/css/form.css` | KEEP | Budget form styling. |
| `static/css/variables.css` | KEEP | Design tokens. |
| `static/css/animations.css` | KEEP | Shared animation helpers. |
| `static/css/responsive.css` | KEEP | Responsive shell behavior. |
| `expense-module/frontend/style.css` | IGNORE | Older standalone auth prototype. |
| Streamlit inline CSS in `dashboard.py` | MERGE CONCEPT ONLY | Rich expense layout ideas, but not directly usable in Flask/Jinja. |

CSS notes:

- Main `static/css/style.css` is a more mature auth screen than the expense frontend prototype.
- Main `base.html` uses Font Awesome.
- Main `main_dashboard.html` uses Bootstrap Icons and Bootstrap CDN.
- The project currently has two visual shell directions. A future integration should choose one canonical sidebar/dashboard shell to avoid CSS conflicts.

## JavaScript

| File | Classification | Why |
|---|---|---|
| `static/js/script.js` | KEEP | Main auth UI JS preserves native form submit. |
| `static/js/main.js` | KEEP | Sidebar toggle and toast helper. |
| `static/js/dashboard.js` | KEEP | Budget filter/modal/delete behavior. |
| `static/js/form.js` | KEEP | Budget form validation. |
| `static/js/charts.js` | MERGE | Currently static demo dashboard charts; should later connect to real expense data. |
| `expense-module/frontend/script.js` | IGNORE | Prevents submit and logs only to console. |
| `expense-module/frontend/react.jsx` | IGNORE | React auth prototype, not part of current Flask stack. |

JavaScript notes:

- Main `static/js/script.js` allows native login/register form submission and adds loading feedback.
- Expense `frontend/script.js` prevents both auth form submissions with `e.preventDefault()`, so copying it would break auth.
- Main `charts.js` currently uses static demo data for dashboard charts. It can be converted later to consume JSON expense endpoints.

## Static Assets

No actual image/static media assets were found in either project. The static layer is mostly CSS, JS, and external CDN resources.

Classification:

| Asset Type | Classification | Why |
|---|---|---|
| Main `static/css` | KEEP/MERGE | Current app styling lives here. |
| Main `static/js` | KEEP/MERGE | Current app behavior lives here. |
| Expense `frontend` | IGNORE/MERGE CONCEPT ONLY | Prototype auth assets, not wired to Flask static paths. |
| CDN fonts/icons/charts | MERGE CAREFULLY | Current project mixes Font Awesome, Bootstrap Icons, Bootstrap, Chart.js, and Google Fonts. |

## Sidebar Navigation

Main has two sidebar approaches:

- `templates/base.html` has Dashboard, Budgets, Create Budget, Logout.
- `templates/main_dashboard.html` has a richer nav: Dashboard, Income, Expenses, Budget, Goals, Investments, Transactions, Reports, Settings, Logout.
- Streamlit dashboard has the same richer navigation labels internally.

Classification: MERGE navigation intent into one canonical Flask sidebar.

Immediate navigation issue:

- `main_dashboard.html` links to `/expenses`.
- Main `app.py` defines `/expense`, singular.
- `/expense` renders missing `expense.jsx`.

Future integration should decide one canonical route:

- Prefer `/expenses` if aligning with existing sidebar labels.
- Or keep `/expense` and update links consistently.

Do not leave both without redirects or clear endpoint names.

## Duplicate Files

| Duplicate / Near Duplicate | Classification | Why |
|---|---|---|
| `database/db.sql` and `expense-module/database/db.sql` | IGNORE | Both are empty and identical. |
| `app.py` in both projects | KEEP main, IGNORE expense | Expense app duplicates auth and conflicts with main schema/session. |
| `db.py` in both projects | KEEP main, MERGE expense transaction pieces | Main is canonical; expense has useful transaction model. |
| `templates/login.html` in both | KEEP main, IGNORE expense | Main version is integrated and styled. |
| `templates/dashboard.html` in both | KEEP main, IGNORE expense | Expense version is placeholder. |
| `frontend/script.js` vs `static/js/script.js` | KEEP main, IGNORE expense | Main submits forms; expense prototype blocks them. |
| `README.md` in both | IGNORE | Both only contain `# FinSight`. |
| `desktop.ini`, `__pycache__`, logs, `env/` | IGNORE | OS/generated/runtime artifacts. |

## Dependencies

Current `requirements.txt`:

```txt
Flask==3.0.3
psycopg2-binary==2.9.10
Werkzeug==3.0.4
python-dotenv==1.0.1
```

Expense module imports additional packages in `db.py` and Streamlit dashboard:

| Dependency | Needed For Integration? | Classification |
|---|---:|---|
| `bcrypt` | Only if preserving expense auth hashes. Prefer not needed if keeping Werkzeug. | IGNORE or MERGE only for migration |
| `streamlit` | Only for current expense dashboard prototype. Not needed in Flask integration. | IGNORE |
| `pandas` | Used for Streamlit CSV/export and analytics. Can be avoided in Flask. | IGNORE initially |
| `plotly` | Used for Streamlit charts. Main already uses Chart.js CDN. | IGNORE initially |
| `psycopg2-binary` | Already present. | KEEP |
| `python-dotenv` | Already present. | KEEP |
| `Werkzeug` | Main auth hashing. | KEEP |

Dependency recommendation:

- Do not add Streamlit dependencies for a Flask integration.
- Do not add React tooling unless intentionally converting the app to a frontend build pipeline.
- Do not add bcrypt unless there is a real migration requirement for existing bcrypt-hashed expense users.
- Use existing Chart.js for expense charts where possible.

## Per-File Classification

| File | Classification | Why |
|---|---|---|
| `app.py` | KEEP | Main Flask controller and integration target. |
| `db.py` | MERGE | Keep existing budget/auth DB helpers; add transaction helpers later. |
| `config.py` | KEEP | Main centralized env config. |
| `requirements.txt` | MERGE | Keep current; add only truly needed expense deps later. |
| `README.md` | IGNORE | Empty/minimal content. |
| `login_app.py` | IGNORE | Separate/old auth entrypoint, not wired into main app. |
| `budget_app.py` | IGNORE | Older standalone auth app, superseded by main `app.py`. |
| `backend/auth.py` | IGNORE | Unsafe/stale blueprint not registered. |
| `backend/login.py` | IGNORE | Empty. |
| `backend/budget.py` | IGNORE | Standalone budget app already folded into main app. |
| `backend/budget_db.py` | IGNORE | Superseded by main `db.py` unless specific missing helper is needed later. |
| `database/schema.sql` | MERGE | Keep existing schema; add `transactions`. |
| `database/db.sql` | IGNORE | Empty. |
| `templates/base.html` | MERGE | Keep shell, add expense nav item later. |
| `templates/login.html` | KEEP | Canonical auth page. |
| `templates/main_dashboard.html` | MERGE | Dashboard UI has Expenses nav and chart areas, but static data. |
| `templates/dashboard.html` | KEEP | Authenticated landing/dashboard summary. |
| `templates/budget_dashboard.html` | KEEP | Budget module UI. |
| `templates/budget_form.html` | KEEP | Budget create/edit UI. |
| `static/css/animations.css` | KEEP | Shared animation helpers. |
| `static/css/app.css` | KEEP | Main shared app shell/sidebar styling. |
| `static/css/budget.css` | KEEP | Budget dashboard styling. |
| `static/css/form.css` | KEEP | Budget form styling. |
| `static/css/main_dashboard.css` | MERGE | Useful dashboard/sidebar styling, but needs reconciliation with the canonical shell. |
| `static/css/responsive.css` | KEEP | Responsive shell behavior. |
| `static/css/style.css` | KEEP | Main auth styling; adapted to Flask. |
| `static/css/variables.css` | KEEP | Design tokens. |
| `static/js/charts.js` | MERGE | Static dashboard charts should later be wired to real data. |
| `static/js/dashboard.js` | KEEP | Budget dashboard interactions. |
| `static/js/form.js` | KEEP | Budget form validation. |
| `static/js/main.js` | KEEP | Sidebar toggle and toast behavior. |
| `static/js/script.js` | KEEP | Auth page interactions and real form submission. |
| `expense-module/app.py` | IGNORE | Standalone auth app conflicts with main. |
| `expense-module/db.py` | MERGE | Extract transaction table and auth hashing lessons only. |
| `expense-module/backend/login.py` | IGNORE | Empty. |
| `expense-module/database/db.sql` | IGNORE | Empty. |
| `expense-module/templates/login.html` | IGNORE | Placeholder auth page with wrong field names. |
| `expense-module/templates/register.html` | IGNORE | Placeholder auth page with wrong field names. |
| `expense-module/templates/dashboard.html` | IGNORE | Placeholder dashboard page. |
| `expense-module/frontend/login.html` | IGNORE | Static prototype superseded by main login page. |
| `expense-module/frontend/style.css` | IGNORE | Static auth prototype styling superseded. |
| `expense-module/frontend/script.js` | IGNORE | Blocks real form submission. |
| `expense-module/frontend/react.jsx` | IGNORE | React prototype not used by Flask app. |
| `expense-module/src/views/dashboard.py` | MERGE CONCEPT ONLY | Contains expense CRUD, analytics, category rules, sidebar ideas, but in Streamlit. |
| `expense-module/README.md` | IGNORE | Minimal content only. |
| `expense-module/desktop.ini` | IGNORE | OS artifact. |
| `.env` | KEEP | Existing environment file; not analyzed for values. |
| `.gitignore` | KEEP | Repository metadata. |
| `desktop.ini` | IGNORE | OS artifact. |
| `flask-server.err.log` | IGNORE | Runtime log. |
| `flask-server.out.log` | IGNORE | Runtime log. |
| `__pycache__/` | IGNORE | Generated Python cache. |
| `env/` | IGNORE | Local virtual environment. |

## Integration Risks

1. Route mismatch:
   - Dashboard sidebar points to `/expenses`.
   - Main app has `/expense`.
   - Existing `/expense` route renders a missing `expense.jsx`.

2. Auth schema conflict:
   - Main user table uses `username` and `password_hash`.
   - Expense module user table uses `name` and `pwd`.

3. Session mismatch:
   - Main Flask app uses `uid`.
   - Expense Flask uses `name`.
   - Streamlit dashboard uses `st.session_state`.

4. Framework mismatch:
   - Main app is Flask/Jinja.
   - Expense dashboard is Streamlit.
   - Expense frontend auth prototype includes React but the main project has no React build pipeline.

5. SQL dialect mismatch:
   - Expense Streamlit code includes PostgreSQL syntax in some places and MySQL-style `YEARWEEK()` in another.

6. Security scoping:
   - Streamlit update/delete transaction helpers do not scope by `user_id`.

7. Dependency creep:
   - Copying Streamlit dashboard wholesale would add Streamlit, pandas, and Plotly without matching the current Flask architecture.

## Recommended Integration Direction

Use main `app.py`, main auth, main session keys, and main schema as the base.

Recommended later implementation sequence:

1. Add `transactions` table to `database/schema.sql`, using main `users(id)` as the foreign key.
2. Add transaction CRUD helpers to main `db.py`.
3. Fix the route mismatch by choosing `/expenses` or `/expense`.
4. Replace the broken `expense.jsx` render with a real Jinja template.
5. Port expense create/read/update/delete behavior from Streamlit into Flask routes.
6. Port category inference either into a Python helper or frontend JS.
7. Reuse existing Chart.js for expense charts instead of bringing Plotly into Flask.
8. Add Expenses to the canonical sidebar.
9. Keep main auth unchanged.
10. Ignore placeholder duplicate auth files.

## Final Recommendation

KEEP the main project as the source of truth.

COPY no files wholesale from the expense module.

MERGE only:

- `transactions` schema concept
- expense CRUD behavior
- expense analytics concepts
- category auto-classification idea
- payment mode field
- sidebar navigation intent

IGNORE:

- expense standalone Flask app
- expense auth templates
- expense frontend auth prototype
- expense React prototype
- empty SQL files
- Streamlit framework code as executable Flask code

Stop here as requested.
