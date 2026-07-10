# 🧪 bgmon Testing Guide

> **Regel:** Vor jedem Push: `python -m pytest tests/... -v`. Kein Push ohne grün.

---

## Infrastruktur

Tests laufen gegen **echte PostgreSQL** — lokal über `bgmon-postgres` Docker-Container, in CI über GitHub Actions Service-Container.

**Lokal (einmalig):**
```bash
docker exec bgmon-postgres psql -U bgmon -d postgres \
  -c "DROP DATABASE IF EXISTS test_bgmon;" \
  -c "CREATE DATABASE test_bgmon OWNER bgmon;"
```

Die DB `test_bgmon` ist separat von `bgmon` — keine Produktivdaten werden berührt.

---

## Tests ausführen

```bash
cd backend

# Alle Tests (empfohlen vor Push)
python -m pytest \
  tests/test_libre_data.py \
  tests/test_alarm_evaluator.py \
  tests/test_auth.py \
  tests/test_notification_profiles.py \
  tests/test_users_api.py \
  tests/test_settings_api.py \
  tests/test_log_api.py \
  tests/test_leader_election.py \
  tests/test_twilio_caller.py \
  tests/test_web_push.py \
  tests/test_dashboard.py \
  tests/test_shifts_night_family.py \
  -v

# Einzelne Datei / Test
python -m pytest tests/test_libre_data.py -v
python -m pytest tests/test_auth.py::TestLogin::test_login_valid_credentials -v
```

> Alte Tests (`test_endpoints.py`, `test_transactions_and_integrity.py`, `test_libre_and_alarms.py`) sind noch nicht migriert — werden im CI ignoriert.

---

## Neue Tests schreiben

### Verfügbare Fixtures (`tests/conftest.py`)

| Fixture | Beschreibung |
|---------|-------------|
| `client` | Flask-Test-Client |
| `db_session` | Saubere DB-Session (DELETE vor/nach Test) |
| `patient_user` | Patient + `_session` Token |
| `observer_user` | Observer + Telefon + `_session` |
| `admin_user` | Admin + `_session` |
| `inactive_user` | Deaktivierter User + `_session` |
| `thresholds` | Schwellwerte 54/70/180/250 |
| `notification_profile_with_assignments` | PUSH für alle 4 Thresholds |
| `notification_profile_with_call` | CALL für critical, PUSH für low/high |
| `glucose_readings` | 24 Readings über 4h |
| `glucose_reading_normal` | sgv=120 |
| `glucose_reading_critical_low` | sgv=50 |
| `night_profile` | 22:00-06:00 enabled |
| `snooze_presets` | 5/15/30 min |
| `family_token` | FamilyDashboardToken |
| `global_settings` | GlobalSettings |
| `auth_headers` | `auth_headers(user)` → `{"Authorization": "Bearer <token>"}` |

### Beispiel

```python
from http import HTTPStatus

class TestSomething:
    def test_happy_path(self, client, patient_user):
        resp = client.get("/api/endpoint", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.OK

    def test_error_case(self, client):
        resp = client.get("/api/endpoint")
        assert resp.status_code == HTTPStatus.UNAUTHORIZED
```

### Externe Services mocken

```python
from unittest.mock import patch
with patch("bgmon_api.services.alarm_evaluator.send_push_to_user") as mock_push:
    # ...
    mock_push.assert_called_once()
```

---

## CI (GitHub Actions)

- Schema via `create_all()` im `app` Fixture (keine Migrationen)
- PostgreSQL 16 Service-Container
- `ruff check bgmon_api` + `ty check bgmon_api` (continue-on-error)
- Tests: explizite Liste der 12 Dateien

---

## Bekannte xfails (nur CI)

| Test | Grund |
|------|-------|
| `test_login_rate_limited` | Rate-Limiting fehlt |
| `test_admin_can_list_all_users` | DetachedInstanceError |
| `test_admin_can_create_user` | `auth_headers()` Aufruf-Fehler |
| `test_admin_can_deactivate_and_reactivate_user` | DetachedInstanceError |
