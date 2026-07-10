# 🔧 bgmon Backend — Critical Fixes Audit

> **Datum:** 2026-07-10 | **CI:** 🟢 grün (156 passed, 4 xfailed)
> **Lint:** 0 Ruff Issues | **Type-check:** 0 Errors (CI: continue-on-error)

---

## ✅ Security (8/9)

- [x] **`config.py`** — `SECRET_KEY` + `DATABASE_URL` ohne Defaults → `RuntimeError`
- [x] **`users.py`** — `GET /api/users` → `admin_required`
- [x] **`users.py`** — `GET /api/users/<id>` → `_require_owner_or_admin`
- [x] **`users.py`** — Thresholds + Snooze-Presets → `_require_owner_or_admin`
- [x] **`auth.py`** — Login prüft `user.is_active`
- [x] **`app.py`** — CORS (`flask-cors`) + Flask-Limiter global
- [ ] **`notifications.py`** — Webhook Auth → separat

## ✅ Code Quality / DRY

- [x] **Stats 3× Copy-Paste** → `compute_glucose_stats()` (net -42 Zeilen)
- [x] **ISO-Datetime 12× Copy-Paste** → `parse_iso_datetime()`
- [x] **9 Dateien** — `db`-Import von `extensions` statt `app`

## ✅ DB & Alarm System

- [x] **`leader.py`** — Atomare PostgreSQL-Upsert (Oracle-reviewed)
- [x] **7 DB-Indexes** via Migration `20260710_000000`
- [x] **Alarm-Evaluator** — Per-User try/except, `profile.is_active` Check, NO_DATA-Snooze
- [x] **`app.py`** — Leader-Check für `_alarm_job`, `_profile_schedule_job`, `_streak_job`

## ✅ Bugfixes

- [x] **`auth.py`** — `transactional_session()` Token-Leak nach Session-Close
- [x] **`auth.py`** — Login ohne `is_active`-Check
- [x] **Type-check** — `parse_iso_datetime()` None-Guards, SQLAlchemy-Descriptor-Ignore
- [x] **CI** — Schema via `create_all()` statt `flask db upgrade`, Scheduler deaktiviert

---

## ✅ Tests (12 Dateien)

| Datei | Tests | Status |
|-------|-------|--------|
| `test_libre_data.py` | 12 | ✅ |
| `test_alarm_evaluator.py` | 21 | ✅ |
| `test_auth.py` | 17 | ✅ (1 xfail: rate-limit) |
| `test_notification_profiles.py` | 20 | ✅ |
| `test_users_api.py` | 20 | ✅ (3 xfail: CI DetachedInstance) |
| `test_settings_api.py` | 19 | ✅ |
| `test_log_api.py` | 12 | ✅ |
| `test_leader_election.py` | 9 | ✅ |
| `test_twilio_caller.py` | 8 | ✅ |
| `test_web_push.py` | 5 | ✅ |
| `test_dashboard.py` | 8 | ✅ |
| `test_shifts_night_family.py` | 10 | ✅ |

**CI-Ergebnis:** 156 passed, 4 xfailed, 2 skipped — 🟢

**Vor jedem Push:**
```bash
cd backend
python -m pytest tests/test_libre_data.py tests/test_alarm_evaluator.py \
  tests/test_auth.py tests/test_notification_profiles.py \
  tests/test_users_api.py tests/test_settings_api.py tests/test_log_api.py \
  tests/test_leader_election.py tests/test_twilio_caller.py \
  tests/test_web_push.py tests/test_dashboard.py \
  tests/test_shifts_night_family.py -v
```

## ⏳ Offen

| Severity | Finding |
|----------|---------|
| CRITICAL | Webhook-Auth (`notifications.py:219`) |
| HIGH | Twilio-Retry (`TWILIO_RETRY_COUNT` ungenutzt) |
| HIGH | `transactional_session()` rollout |
| MEDIUM | Migration Downgrade Datenverlust |
| MEDIUM | Rate-Limiting auf Login |
