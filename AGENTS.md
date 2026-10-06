# bgmon — Development Guidelines

## Projekt
- Blutzucker-Monitoring PWA. Stack: Flask (+ SQLAlchemy + InfluxDB + Twilio + Scikit-Learn) in `backend/`, Svelte 5 / Vite / TypeScript in `frontend/`. Alles in einem Repo, Docs im Root (README.md, AGENTS.md, TODO.md, DESIGN.md, ML.md).
- Zwei Remotes — **immer beide pushen**: `origin` (git.familie-heise.de/daniel/bgmon) und `github` (github.com/mcfetz).
- Commits im Conventional Commits Stil. Keine Code-Kommentare außer explizit angefragt.
- Main hat keinen Branch-Schutz — Merge-Stil: `gh pr merge <n> --rebase` (linear).

## MCP Tools (immer nutzen!)
- **`mcp__jdocemunch__*`** — für Codebase-Orientierung (Symbol suchen, Dependencies tracen, Callgraphs). Nie Read/Grep/Glob/Bash für Code-Exploration (Ausnahme: `Read` direkt vor einem `Edit`/`Write`).
- **`ntfy_ntfy_me`** — Completion-Notification (siehe unten). Server: `https://ntfy.familie-heise.de/`, Topic/Token über `NTFY_TOPIC`/`NTFY_TOKEN`.
- **`playwright`** — für E2E-Tests im Browser (falls nötig).
- **`context7`** — für Library Docs (Svelte, Flask, SQLAlchemy).

### Code Exploration Policy
1. `resolve_repo { "path": "." }` — bestätigen, dass das Repo indexiert ist, sonst `index_folder`.
2. `suggest_queries` — bei unbekanntem Repo.
- Symbol finden → `search_symbols` (Filtern via `kind=`, `language=`, `file_pattern=`, `decorator=`). Abwesenheit nur akzeptieren, wenn `_meta.verdict` das eindeutig belegt (`absence_citable`/`citable`); sonst NICHT weiter raten, sondern melden: "No existing implementation found for X."
- Strings/Kommentare/Config → `search_text` (Regex, `context_lines`).
- Vor dem Öffnen einer Datei → `get_file_outline`; Symbole → `get_symbol_source` (oder `get_context_bundle` für Imports); Zeilenbereich → `get_file_content`.
- Impact: `find_importers`, `find_references`/`check_references`, `get_dependency_graph`, `get_blast_radius`.
- Nach Edits: `register_edit` mit den geänderten Dateipfaden (Caches invalidieren; ggf. `index_file`).

### Session-Aware Routing
- Task-Beginn: `plan_turn { "repo": ".", "query": "<task>", "model": "<model-id>" }` → Confidence (high → direkt zu Symbolen, max 2 Zusatz-Reads; medium → max 5; low → Feature existiert vermutlich nicht, Gap melden).
- Konkreter Task: `assemble_task_context` nutzt ein Capsule (Token-budgetiert, auto-intent).
- Token-Sparsamkeit: `_meta.budget_warning` beachten und nicht weiter suchen; `get_session_context` gegen Doppel-Lesen.

## Backend

### Layout
- `bgmon_api/app.py` — Flask factory, Scheduler, Blueprint-Registrierung
- `bgmon_api/extensions.py` — `db`, `migrate` (einzige Quelle, kein Circular Import)
- `bgmon_api/models.py` — SQLAlchemy Models, `__getattr__` für lazy `db` Import
- `bgmon_api/auth_utils.py` — `get_current_user()`, `admin_required()`, **lazy imports** für Models
- `bgmon_api/routes/` — Blueprints: auth, users, dashboard, log, night, shifts, alarms, family, settings, notifications
- `bgmon_api/services/` — `libre_fetcher`, `alarm_evaluator`, `twilio_caller`, `web_push`, `leader`, `influx_reader`

### Commands
```bash
cd /home/daniel/development/bgmon/backend
source .venv/bin/activate
flask db migrate -m "message"   # create migration
flask db upgrade               # apply
flask db stamp <rev>            # mark applied (without executing)
ruff check .                    # lint
ruff check --fix .              # auto-fix
ty check .                      # type check
python -m compileall -q bgmon_api/  # syntax check
pytest tests/ -q --tb=short     # tests (läuft gegen separate Test-DB)
```
Hinweis: `backend/pyproject.toml` definiert `[project.optional-dependencies] dev` (pytest, ruff, ty, …); Kanon des Locks ist `uv.lock` (Dependabot), lokale Checks laufen über das pip-basierte `.venv`.

### Backend starten (Dev)
```bash
lsof -ti:5000 | xargs kill -9 2>/dev/null
cd /home/daniel/development/bgmon/backend
source .venv/bin/activate
export FLASK_APP=bgmon_api.app:create_app FLASK_ENV=development
setsid nohup python -u -m flask run --host=0.0.0.0 --port=5000 --no-reload --with-threads > /tmp/bgmon-backend.log 2>&1 < /dev/null & disown
```

## Frontend

### Layout
- `src/routes/+page.svelte` — Dashboard (Graph, Log, Settings, Stats)
- `src/lib/components/` — GlucoseGraph, LogEntryForm, LogHistory, SettingsDialog, ProfileSelector, NightProfile, Report*, etc.
- `src/lib/api/` — API-Clients (dashboard, log, auth, report)
- Alias `$lib` seit SvelteKit 3 = Subpath-Import `#lib` (Mapping in `frontend/package.json` → `imports`), SvelteKit-Config in `frontend/vite.config.ts` (kein `svelte.config.js` mehr).

### Commands
```bash
cd /home/daniel/development/bgmon/frontend
npm run check      # svelte-check (0 errors Ziel)
npm run build      # production build (adapter-static → dist)
npm test           # vitest
npm run lint       # prettier --check + eslint (Formating 0, keine neuen Errors)
npm run preview    # serve build (Port 4173 by default)
```

### Frontend starten
```bash
lsof -ti:5173 | xargs kill -9 2>/dev/null
cd /home/daniel/development/bgmon/frontend
setsid nohup npx vite preview --host 0.0.0.0 --port 5173 > /tmp/bgmon-frontend.log 2>&1 < /dev/null & disown
```

## Quality assurance (Pflicht, bevor ein Work Item geschlossen wird)
Backend (`backend/`, in `.venv`):
- `ruff check .` → 0 findings
- `ty check .` → 0 errors
- `python -m compileall -q bgmon_api/` → 0
- `pytest tests/ -q --tb=short` → grün (Tests laufen isoliert gegen eine Test-DB, siehe `backend/tests/conftest.py`; Test-DB-URL via `BGMON_TEST_DATABASE_URL` oder Default `test_bgmon`, erwartet `"test"` im DB-Namen, damit die Dev-DB nie angetastet wird)

Frontend (`frontend/`):
- `npm run lint` → prettier sauber, eslint ohne neue Errors (bekannte Altlasten: `no-explicit-any` in `src/routes/+page.svelte`)
- `npm run check` → 0 errors
- `npm run build` → grün
- `npm test` → grün

Schnellcheck: `./scripts/check.sh backend` bzw. `frontend` (ruff/ty/compileall + ntfy). Nach JEDER Implementierung: ruff → ty → compileall → Tests → ntfy.

## Enforced Gates
- **`.pre-commit-config.yaml`**: Backend-Hooks (ruff, ty, compileall via `.venv`) laufen vor jedem Commit — nur wenn `backend/.*\.py$` gestaged ist. Einmalig `uv tool install pre-commit` + `pre-commit install`.
- **`.github/workflows/ci.yml`**: job `backend` (ruff check . / ty check . / pytest), job `frontend` (lint/check/test/build), `docker-build` + Portainer `deploy`-Webhook auf jedem Push/PR zu `main`. Lint dort `continue-on-error` für bekannte Altlasten.
- **Main** ist nicht branch-geschützt; mergen via `gh pr merge <n> --rebase`.
- **Version Pinning**: ruff/ty leben in `[project.optional-dependencies] dev` (`backend/pyproject.toml`), Frontend-Scripts frozen via `frontend/package-lock.json` (`npm ci`). GitHub-Action-Refs exakt pinnen (z. B. `actions/checkout@v7`, kein rolling Tag).
- **Dependabot**: Minor/Patch-PRs mergen; Major-Bumps kritisch reviewen (besonders DB/ORM wie SQLAlchemy, oder Framework-Migrationen wie SvelteKit). Dependabot-Branches ggf. via `git worktree` + `--force-with-lease` rebase/schieben, Konflikte im Lockfile per Re-Generierung (`npm install` / `uv lock`) lösen.

## Gotchas (bereits passiert, nicht wieder!)

### 1. Doppelte Funktionsdefinitionen
- Python nimmt die LETZTE Definition. Beim Umschreiben: `grep -n "def funcname"` prüfen, ob ALTE Definitionen weiter unten existieren! Ruff/ty finden das (IMMER Checks laufen lassen).

### 2. Circular Import `models.py` ↔ `app.py`
- `db` kommt aus `extensions.py`; `models.py` macht lazy `db`-Import via `__getattr__`. `auth_utils.py` und `alarm_evaluator.py` machen **lazy imports INNERHALB der Funktionen**.

### 3. PostgreSQL ENUM Case-Sensitivity
- SQLAlchemy sendet bei `enum.StrEnum` den Member-Name (UPPERCASE), nicht den Value. Migration muss Enum UPPERCASE anlegen, sonst `InvalidTextRepresentation`. Bestehende Daten mit `CASE WHEN` mappen.

### 4. Leader Election blockiert Alarm-Job
- `_alarm_job` läuft nur als Leader. Single-Instance: Leader-Check entfernen oder im Test-Modus direkt aufrufen. Scheduler darf nie doppelt starten.

### 5. `backdrop-filter` erzeugt neuen "containing block"
- `position: fixed`-Modale innerhalb von `backdrop-filter` werden relativ zum Parent positioniert. → `backdrop-filter` vermeiden oder Modal per Portal/Teleport außerhalb rendern (Svelte 5: `{@render}`/Fragment außerhalb).

### 6. `button onclick` ohne Arrow-Function
- Svelte 5: `onclick={func}` übergibt das Event als ersten Parameter → `onclick={() => func()}` ist sicherer.

### 7. Flask Reloader startet App doppelt → doppelte Jobs
- `FLASK_ENV=development` aktiviert den Reloader → `flask run --no-reload` verwenden (oder Idempotency-Guard in `create_app()`). Symptom: `duplicate key value violates unique constraint "user_snoozes_pkey"`.

### 8. Modal Dark-Mode Background
- Nur **BgModal** nutzt im Dark-Mode schwarz; alle anderen Modals (TirModal, SnoozeModal, SettingsDialog) folgen `var(--color-surface)`. Kein `background: #000` per `prefers-color-scheme` in anderen Modals.

### 9. Threshold pro User, nicht pro Patient
- `POST /api/settings/thresholds` speichert für den eingeloggten `user.id`. Alarm-Evaluator prüft jeden User gegen seinen eigenen Threshold. Patient und Admin können unterschiedliche Schwellwerte haben.

### 10. Tests nie gegen die Dev-DB
- Conftest erzwingt eine separate Test-DB (`"test"` im Namen). Nie mit `BGMON_DATABASE_URL` auf `bgmon` testen.

## Datenbank Models (Übersicht)
- `users` — email, display_name, phone_number, twilio_from_number, role, is_active
- `sessions` — auth tokens
- `night_profiles` — Nachtschicht-Einstellungen
- `shifts` — Schicht-Management
- `push_subscriptions` — Web Push
- `log_entries` — entry_type (carbs/insulin/basal/note), value, unit, notes
- `alarms` — alarm_type (critical_low/low/high/critical_high/no_data), sgv
- `twilio_call_logs` — Anruf-Logs
- `scheduler_leader` — Leader Election
- `snooze_presets` — Snooze-Vorlagen
- `carb_factor_history` — KE-Faktor Verlauf
- `NotificationProfile` / `NotificationAssignment` (UNIQUE(profile_id, threshold)) / `UserActiveProfile` / `UserSnooze`
- `thresholds` — Per-User Schwellwerte
- `glucose_readings` — Primary Storage (PostgreSQL)
- `family_dashboard_tokens` — Family Dashboard Access

## API Endpoints (alle)
`GET /health` · `/api/auth/*` · `/api/users/*` · `/api/dashboard/*` (current, history, stats, logs, thresholds) · `/api/log/*` · `/api/night/*` · `/api/shifts/*` · `/api/alarms/*` · `/api/family/*` · `/api/settings/*` (global, thresholds, email, password, twilio) · `/api/notifications/*` (profiles, active, snooze)

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
BGMON_TEST_DATABASE_URL=postgresql://bgmon:bgmon@localhost:5432/bgmon_test
```

## Known Issues / TODO
Siehe `TODO.md`

## Completion notification via ntfy

### When
- **Immer wenn ein Work Item fertig ist**: Checks (lint/build/tests) grün UND auf alle Remotes gepusht. Nie vor dem Push, nie für lediglich geplante/gestoppte lokale Arbeit.
- **Eine Notification pro Work Item**, nicht pro Commit (mehrere Commits → eine Zusammenfassung mit allen SHAs).
- Keine Notifications für: Zwischenzustände, rein informative Antworten, Fragen, unverifizierte Arbeit.
- Optional empfohlen: kurze Fehler-Notification, wenn Arbeit blockiert/abgebrochen wurde (Was? Warum? Was ist offen?).

### What to include
- Kurzer Titel: `<projektname>: <thema> <status>` (z. B. `bgmon: Deps-Update + CI grün`).
- Message: 2–4 Sätze in der Sprache des Users:
  1. was gemacht wurde (Kernpunkte, keine Dateiliste),
  2. letzte Commit-SHAs + dass auf alle Remotes gepusht wurde,
  3. Verifikationsergebnis (z. B. "Ruff/ty/pytest grün, frontend check/build/tests grün"),
  4. offene Risiken/Warnungen.
- Keine Secrets, keine langen Logs, kein Markdown nötig (ntfy rendert Plain Text).

### How (in opencode)
- Tool `ntfy_ntfy_me` mit `title` + `message`; Server/Topic aus Env `NTFY_URL` handelt die Familie-Heise-URL ab, Topic via `NTFY_TOPIC`; Token falls nötig über `NTFY_TOKEN`/`accessToken`, **nie hardcoden**.
- Ohne dediziertes Tool (curl):
  `curl -d "message" -H "Title: bgmon: …" "https://ntfy.familie-heise.de/$NTFY_TOPIC"`

### Reference example
Title: `bgmon: SvelteKit-3-Migration + alle PRs gemerged`
Message: `SvelteKit 3.0.0 migriert (sv migrate, $lib→#lib, cookie ^2.0.1). 6 Dependabot-PRs gemerged (letzte main: d27733d), beide Remotes gepusht. Checks: backend ruff/ty/pytest + frontend check/build/test grün, Prod health 200.`

## Replication template (für andere Repos)
QA-Basis in einem anderen Repo aufsetzen:
1. **Backend (Python):** ruff/ty als Test-Dev-Dependency; `[tool.ruff]` mit passendem `target-version`, `extend-exclude` nur für generierte Ordner (mit Begründung); Findings auf 0 fixen (breite excepts nur mit `# noqa` + Begründung).
2. **CI:** `.github/workflows/ci.yml` `job backend` (checkout, setup, `pip install -e ".[dev]"` o. `uv sync --frozen`, dann `ruff check .` / `ty check .`) + `job frontend` (`npm ci`, `npm run lint`/`build`/`test`) + Docker-Build + Deploy-Webhook.
3. **Pre-commit:** `.pre-commit-config.yaml` im Root — lokale Hooks, `entry: bash -c 'cd <dir> && …'`, `language: system`, `pass_filenames: false`, Scope auf `^backend/.*\.py$`. Einmalig `pre-commit install`.
4. **Branch protection** (falls gewünscht): `gh api --method PUT repos/<owner>/<repo>/branches/main/protection` mit `required_status_checks` auf die Job-Namen.
5. **Completion criteria:** alle Checks = 0/grün, CI-Run auf GitHub grün, Hooks laufen lokal, beide Remotes gepusht, ntfy.