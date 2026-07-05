# bgmon — Agent Guide

## Projekt
- **Stack:** Flask + Svelte 5 + PostgreSQL + InfluxDB + Twilio
- **Repo:** `/home/daniel/development/bgmon`
- **Doku:** README.md, AGENTS.md, TODO.md (alle im Root)

## MCP Tools (immer nutzen!)
- **`mcp__jdocemunch__*`** — für Codebase-Orientierung (Symbol suchen, Dependencies tracen, Callgraphs)
- **`ntfy_ntfy_me`** — für Notifications (z.B. nach jedem Check, Deployment, Alarm)
- **`playwright`** — für E2E-Tests im Browser
- **`context7`** — für Library Docs (Svelte, Flask, SQLAlchemy)

## Backend

### Layout
- `bgmon_api/app.py` — Flask factory, Scheduler, Blueprint-Registrierung
- `bgmon_api/extensions.py` — `db`, `migrate` (einzige Quelle, kein Circular Import)
- `bgmon_api/models.py` — SQLAlchemy Models, `__getattr__` für lazy `db` Import
- `bgmon_api/auth_utils.py` — `get_current_user()`, `admin_required()`, **lazy imports** für Models
- `bgmon_api/routes/` — Blueprints: auth, users, dashboard, log, night, shifts, alarms, family, **settings, notifications**
- `bgmon_api/services/` — `libre_fetcher`, `alarm_evaluator`, `twilio_caller`, `web_push`, `leader`, `influx_reader`

### Commands
```bash
cd /home/daniel/development/bgmon/backend
source .venv/bin/activate
flask db migrate -m "message"   # create migration
flask db upgrade               # apply
flask db stamp <rev>            # mark applied (ohne auszuführen)
ruff check .                    # linting
ruff check --fix .              # auto-fix
ty check bgmon_api/             # type check
python -m compileall -q bgmon_api/  # syntax check
```

### Backend starten (Dev)
```bash
lsof -ti:5000 | xargs kill -9 2>/dev/null
cd /home/daniel/development/bgmon/backend
source .venv/bin/activate
export FLASK_APP=bgmon_api.app:create_app FLASK_ENV=development
setsid nohup python -u -m flask run --host=0.0.0.0 --port=5000 --no-reload > /tmp/bgmon-backend.log 2>&1 < /dev/null & disown
```

## Frontend

### Layout
- `src/routes/+page.svelte` — Dashboard (Graph, Log, Settings, Stats)
- `src/lib/components/` — GlucoseGraph, LogEntryForm, LogHistory, SettingsDialog, ProfileSelector, NightProfile, etc.
- `src/lib/api/` — API-Clients (dashboard, log, auth)

### Commands
```bash
cd /home/daniel/development/bgmon/frontend
npm run build      # production build
npm run preview    # serve build (Port 4173 by default)
```

### Frontend starten
```bash
lsof -ti:5173 | xargs kill -9 2>/dev/null
cd /home/daniel/development/bgmon/frontend
setsid nohup npx vite preview --host 0.0.0.0 --port 5173 > /tmp/bgmon-frontend.log 2>&1 < /dev/null & disown
```

## WICHTIGE REGELN (vergiss nicht!)

### Nach JEDER Implementierung:
1. **Ruff** ausführen
2. **ty** (type checker) ausführen
3. **python -m compileall** ausführen
4. **ntfy triggern** (Task abgeschlossen / Fehler)

Oder Script nutzen: `./scripts/check.sh backend` bzw. `frontend`

### Gotchas (bereits passiert, nicht wieder!)

#### 1. **Doppelte Funktionsdefinitionen**
- Python nimmt die LETZTE Definition. Wenn du eine Funktion umschreibst, suche mit `grep -n "def funcname"` ob es ALTE Definitionen weiter unten gibt!
- Ruff/ty hätten das gefunden → **IMMER checks laufen lassen**

#### 2. **Circular Import zwischen `models.py` und `app.py`**
- `app.py` importiert Blueprints → Blueprints importieren `models.py` → `models.py` braucht `db`
- **Lösung:** `db` kommt aus `extensions.py` (eigene Datei), `models.py` macht `from bgmon_api.extensions import db`
- `models.py` hat `__getattr__` für lazy `db` Import
- `auth_utils.py` und `alarm_evaluator.py` machen **lazy imports** von Models INNERHALB der Funktionen (nicht am Modulanfang!)

#### 3. **PostgreSQL ENUM Case-Sensitivity**
- SQLAlchemy sendet bei `enum.StrEnum` den **Member-Name** (UPPERCASE), NICHT den Value
- Wenn Migration den Enum mit lowercase erstellt → `InvalidTextRepresentation` Fehler
- **Lösung:** Enum in Migration mit UPPERCASE erstellen, dann `CASE WHEN` für bestehende Daten

#### 4. **Leader Election blockiert Alarm-Job**
- `_alarm_job` läuft nur wenn Instanz Leader ist
- Bei Single-Instance: Leader-Check entfernt oder einfach alle Jobs immer laufen lassen
- **Test-Modus:** `_alarm_job` ohne Leader-Check aufrufen

#### 5. **`backdrop-filter` erzeugt neuen "containing block"**
- `position: fixed` Modale innerhalb von `backdrop-filter` Elementen werden RELATIV zum Parent positioniert (nicht zum Viewport)
- **Lösung:** `backdrop-filter` vermeiden ODER Modal mit Portal/Teleport außerhalb rendern

#### 6. **`button onclick` ohne Arrow-Function**
- Svelte 5: `onclick={func}` übergibt das Event als ersten Parameter
- `onclick={() => func()}` ist sicherer

#### 7. **Flask Reloader startet App doppelt → doppelte Jobs**
- `FLASK_ENV=development` aktiviert Reloader → `create_app()` läuft 2x → 2 BackgroundScheduler → doppelte Jobs
- Symptom: `IntegrityError: duplicate key value violates unique constraint "user_snoozes_pkey"`
- **Lösung:** `flask run --no-reload` ODER Idempotency-Guard in `create_app()` (siehe `app.py`)

#### 8. **Modal Dark-Mode Background**
- Nur der **BgModal** (großer BG-Screen) nutzt im Dark-Mode **schwarz** als Background — weil er auch nachts gezeigt wird und so dunkel wie möglich sein soll.
- **Alle anderen Modals** (TirModal, SnoozeModal, SettingsDialog) folgen dem normalen Farbschema (`var(--color-surface)`).
- Kein `@media (prefers-color-scheme: dark)` mit `background: #000` in anderen Modals.

#### 9. **Threshold pro User, nicht pro Patient**
- `POST /api/settings/thresholds` speichert für `user.id` (den eingeloggten User)
- Alarm-Evaluator iteriert alle User mit aktivem Profil und prüft JEDEN gegen seinen eigenen Threshold
- Patient und Admin können unterschiedliche Schwellwerte haben

## Datenbank Models (Übersicht)
- `users` — email, display_name, phone_number, twilio_from_number, role, is_active
- `sessions` — auth tokens
- `night_profiles` — Nachtschicht-Einstellungen
- `shifts` — Schicht-Management
- `push_subscriptions` — Web Push
- `log_entries` — entry_type (carbs/insulin/basal/**note**), value, unit, notes
- `alarms` — alarm_type (critical_low/low/high/critical_high/no_data), sgv
- `twilio_call_logs` — Anruf-Logs
- `scheduler_leader` — Leader Election
- `snooze_presets` — Snooze-Vorlagen
- `carb_factor_history` — KE-Faktor Verlauf
- **NotificationProfile** — user_id, name, icon, is_active
- **NotificationAssignment** — profile_id, area (push/call), threshold, UNIQUE(profile_id, threshold)
- **UserActiveProfile** — user_id (PK), profile_id — aktives Profil
- **UserSnooze** — user_id (PK), snooze_until, reason
- **thresholds** — Per-User Schwellwerte (critical_low, low, high, critical_high)
- **glucose_readings** — Primary Storage (PostgreSQL)
- **family_dashboard_tokens** — Family Dashboard Access

## Alarm-Flow (komplett)
1. `evaluate_alarms()` läuft alle 30s
2. `query_current_glucose()` aus InfluxDB
3. Prüft Schwellwerte (default oder user-spezifisch)
4. Wenn breached:
   - `UserActiveProfile` für Patient holen
   - `UserSnooze` prüfen (skip wenn aktiv)
   - `NotificationAssignment` für threshold im aktiven Profil holen
   - Bei `call`: `place_call(user, sgv, title)` → Twilio + LogEntry
   - Bei `push`: `send_push_to_user(user.id, title, body)` + LogEntry
   - 15-min Snooze setzen
5. Twilio-Body: `"Der aktuelle Blutzuckerwert beträgt {sgv} Milligramm pro Deziliter. {title}. Bitte überprüfen Sie den Blutzuckerwert des Patienten."`

## API Endpoints (alle)
- `GET /health`
- `/api/auth/*` — login, logout, me
- `/api/users/*` — CRUD
- `/api/dashboard/*` — current, history, stats, logs, thresholds
- `/api/log/*` — CRUD für LogEntry
- `/api/night/*` — NightProfile
- `/api/shifts/*` — Shift Management
- `/api/alarms/*` — Alarms, push, snooze
- `/api/family/*` — Family Dashboard
- `/api/settings/*` — global, thresholds, email, password, twilio (numbers/test)
- `/api/notifications/*` — profiles (CRUD), active (GET/PUT), snooze (GET/POST/DELETE)

## Environment (.env)
```
BGMON_SECRET_KEY=
BGMON_DATABASE_URL=postgresql://bgmon:bgmon@localhost:5432/bgmon
BGMON_TWILIO_ACCOUNT_SID=
BGMON_TWILIO_AUTH_TOKEN=
BGMON_TWILIO_FROM_NUMBER=+491739070444
BGMON_TWILIO_NUMBERS=+4915201634961,+491739070444
BGMON_TWILIO_RETRY_COUNT=3
BGMON_TWILIO_RETRY_DELAY_S=90
BGMON_LEASE_TTL_S=30
BGMON_LEADER_RENEW_S=10
```

## Known Issues / TODO
Siehe `TODO.md`
