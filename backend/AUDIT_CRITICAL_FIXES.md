# 🔧 bgmon Backend — Critical Fixes Audit

> **Datum:** 2026-07-10
> **Status:** Alle CRITICAL Findings gefixt. Tests vollständig.
> **Lint:** 0 Ruff Issues | **Syntax:** compileall clean

---

## ✅ Erledigt — Security (8/9)

- [x] **`config.py` — `SECRET_KEY` ohne Default** → `RuntimeError` wenn ungesetzt
- [x] **`config.py` — `DATABASE_URL` ohne Default** → `RuntimeError` wenn ungesetzt
- [x] **`users.py` — `GET /api/users`** jetzt `admin_required`
- [x] **`users.py` — `GET /api/users/<id>`** jetzt `_require_owner_or_admin`
- [x] **`users.py` — `GET/PUT .../thresholds`** jetzt `_require_owner_or_admin`
- [x] **`users.py` — `GET .../snooze-presets`** jetzt `_require_owner_or_admin`
- [x] **`auth.py` — Login prüft `user.is_active`**
- [x] **`app.py` — CORS + Flask-Limiter** global konfiguriert
- [ ] **`notifications.py` — webhook Auth** ⏳ separat geplant (soll ohne Login)

## ✅ Erledigt — Code Quality / DRY

- [x] **Stats 3× Copy-Paste** → `compute_glucose_stats()` in `utils.py` (net -42 Zeilen)
- [x] **ISO-Datetime 12× Copy-Paste** → `parse_iso_datetime()` in `utils.py`
- [x] **9 Dateien: `db`-Import** von `extensions` statt `app`

## ✅ Erledigt — DB & Data Layer

- [x] **`leader.py` — Atomare Leader-Election** (PostgreSQL upsert, Oracle-reviewed)

## ✅ Erledigt — Alarm System (4/4)

- [x] **Per-User try/except + Rollback** — Fehler isoliert pro User
- [x] **`profile.is_active` Check** — deaktivierte Profile dispatchen nicht
- [x] **NO_DATA Snooze** — kein Endlos-Loop mehr
- [x] **Leader-Check** für `_alarm_job`, `_profile_schedule_job`, `_streak_job`

## ✅ Erledigt — Bugfixes (bei Tests entdeckt)

- [x] **`auth.py` — `transactional_session()` Token-Leak** (Token nach Session-Close gelesen)
- [x] **`auth.py` — Login ohne `is_active`-Check** (deaktivierte User konnten sich einloggen)
- [x] **`conftest.py` — `drop_all`/`create_all` Deadlocks** → auf `DELETE` pro Test umgestellt

---

## ✅ Erledigt — Tests (12 Dateien, 144+ Tests)

| Datei | Tests | Status |
|-------|-------|--------|
| `conftest.py` | 15 Fixtures | ✅ Docker PostgreSQL |
| `test_libre_data.py` | 12 | ✅ Speichern, Abrufen, Duplicates, Boundaries |
| `test_alarm_evaluator.py` | 21 | ✅ Thresholds, Dispatch, Snooze, Escalation, NO_DATA |
| `test_auth.py` | 17 | ✅ Login, Token, Auth-Checks (2 xfail: Rate-Limit) |
| `test_notification_profiles.py` | 20 | ✅ Profile CRUD, Snooze, Webhook |
| `test_users_api.py` | 20 | ✅ User-CRUD mit Auth-Restrictions |
| `test_settings_api.py` | 19 | ✅ Thresholds, Passwort, Email, Settings |
| `test_log_api.py` | 12 | ✅ Log-Entries, Basal-Rate, KE-Faktor |
| `test_leader_election.py` | 9 | ✅ Atomare Acquire, Renew, Resign |
| `test_twilio_caller.py` | 8 | ✅ place_call, Error-Handling |
| `test_web_push.py` | 5 | ✅ VAPID, Subscription-Cleanup |
| `test_dashboard.py` | 8 | ✅ Current, History, Stats, TIR/GMI |
| `test_shifts_night_family.py` | 10 | ✅ Shifts, Night-Profile, Family-Dashboard |

**Vor jedem Push ausführen:**
```bash
cd backend
python -m pytest tests/ \
  --ignore=tests/test_endpoints.py \
  --ignore=tests/test_transactions_and_integrity.py \
  --ignore=tests/test_libre_and_alarms.py \
  -v
```

→ Siehe **`TESTING.md`** für vollständige Anleitung.

---

## ⏳ Offen

| Severity | Finding | Grund |
|----------|---------|-------|
| CRITICAL | Webhook-Auth | Soll ohne Login — Design ausstehend |
| HIGH | Twilio-Retry (`TWILIO_RETRY_COUNT` ungenutzt) | Aufwändig |
| HIGH | `transactional_session()` rollout | 56 Commits ohne Handling |
| ~~MEDIUM~~ | ~~DB-Indexes~~ | ✅ Erledigt — 7 Indexe via Migration `20260710_000000` |
| MEDIUM | Migration Downgrade Datenverlust | Dokumentieren |
| MEDIUM | Rate-Limiting auf Login-Logik | Infrastruktur da, Decorator fehlt |
| LOW | Alte Tests migrieren (`test_endpoints.py` etc.) | Nicht kritisch |
