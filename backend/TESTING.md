# 🧪 bgmon Testing Guide

> **Regel:** Vor jedem Push müssen die Tests laufen. Kein Push ohne grüne Suite.

---

## Infrastruktur

Die Tests laufen gegen eine **echte PostgreSQL-Datenbank** im Docker-Container `bgmon-postgres`:

```bash
# Container muss laufen (wird von docker-compose up gestartet)
docker ps | grep bgmon-postgres

# Test-DB anlegen (einmalig, oder nach DB-Reset)
docker exec bgmon-postgres psql -U bgmon -d postgres \
  -c "DROP DATABASE IF EXISTS test_bgmon;" \
  -c "CREATE DATABASE test_bgmon OWNER bgmon;"
```

**Wichtig:** Die Test-DB `test_bgmon` ist separat von der Entwicklungs-DB `bgmon`. Keine Produktivdaten werden berührt.

---

## Tests ausführen

```bash
cd backend

# Alle neuen Tests (empfohlen vor Push)
python -m pytest tests/ \
  --ignore=tests/test_endpoints.py \
  --ignore=tests/test_transactions_and_integrity.py \
  --ignore=tests/test_libre_and_alarms.py \
  -v

# Alle Tests inkl. alter (wenn sie mal migriert sind)
python -m pytest tests/ -v

# Einzelne Test-Datei
python -m pytest tests/test_libre_data.py -v

# Einzelner Test
python -m pytest tests/test_auth.py::TestLogin::test_login_valid_credentials -v

# Mit Coverage-Report
python -m pytest tests/ --cov=bgmon_api --cov-report=term-missing -v
```

---

## Neue Tests schreiben

### 1. Conftest-Fixtures nutzen

Alle Fixtures sind in `tests/conftest.py` definiert. **Immer diese nutzen, nie eigene DB-Verbindungen aufbauen.**

| Fixture | Beschreibung |
|---------|-------------|
| `client` | Flask-Test-Client (App mit Test-DB) |
| `db_session` | Saubere DB-Session (Tabellen werden vor/nach jedem Test geleert) |
| `patient_user` | Patient-User mit `_session` (Auth-Token) |
| `observer_user` | Observer mit Telefonnummer + `_session` |
| `admin_user` | Admin + `_session` |
| `inactive_user` | Deaktivierter User + `_session` |
| `thresholds` | Default-Schwellwerte für Patient (54/70/180/250) |
| `notification_profile_with_assignments` | Aktives Profil mit PUSH für alle 4 Thresholds |
| `notification_profile_with_call` | Aktives Profil mit CALL für critical, PUSH für low/high |
| `glucose_readings` | 24 GlucoseReadings über 4 Stunden |
| `glucose_reading_normal` | Ein Reading mit sgv=120 |
| `glucose_reading_critical_low` | Ein Reading mit sgv=50 |
| `night_profile` | NightProfile (22:00-06:00, enabled) |
| `snooze_presets` | 3 SnoozePresets (5/15/30 min) |
| `family_token` | FamilyDashboardToken |
| `global_settings` | GlobalSettings (insulin 4h, correction 50) |
| `auth_headers` | Factory: `auth_headers(user)` → `{"Authorization": "Bearer ..."}` |

### 2. Test-Struktur

```python
from http import HTTPStatus

class TestSomething:
    """Gruppiere verwandte Tests in Klassen."""

    def test_happy_path(self, client, patient_user):
        """Jeder Test hat einen beschreibenden Namen."""
        resp = client.get("/api/endpoint", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.OK
        data = resp.get_json()
        assert data["key"] == "expected_value"

    def test_error_case(self, client):
        """Teste auch Fehlerfälle."""
        resp = client.get("/api/endpoint")
        assert resp.status_code == HTTPStatus.UNAUTHORIZED
```

### 3. Regeln

- **Jeder Test ist unabhängig** — `db_session` leert die Tabellen vor/nach jedem Test
- **Keine Source-Code-Änderungen in Tests** — nur Mocks für externe Services (Twilio, VAPID, LibreLinkUp)
- **Echte DB, keine SQLite** — die Tests laufen gegen PostgreSQL (Enum-Types, Constraints etc. werden getestet)
- **Auth-Header immer mitsenden** wenn der Endpoint Auth braucht (die meisten tun das)
- **Externe Services mocken:**
  ```python
  from unittest.mock import patch

  with patch("bgmon_api.services.alarm_evaluator.send_push_to_user") as mock_push:
      # ... test code ...
      mock_push.assert_called_once()
  ```

### 4. Vor dem Commit

```bash
# 1. Ruff check
ruff check tests/ bgmon_api/

# 2. Tests laufen lassen
python -m pytest tests/ \
  --ignore=tests/test_endpoints.py \
  --ignore=tests/test_transactions_and_integrity.py \
  --ignore=tests/test_libre_and_alarms.py \
  -v

# 3. Bei grün: commiten
```

---

## Bekannte Probleme

- **`test_endpoints.py`, `test_transactions_and_integrity.py`, `test_libre_and_alarms.py`** sind alte Tests, die noch auf den neuen Conftest migriert werden müssen. Sie werden aktuell ignoriert.
- **Rate-Limiting auf `/api/auth/login`** ist noch nicht implementiert. Der entsprechende Test (`test_login_rate_limited`) ist als erwarteter Fehlschlag markiert.
- **DB-Deadlocks** können auftreten wenn zu viele Tests parallel laufen. Lösung: `docker restart bgmon-postgres` und DB neu erstellen.

---

## Test-Dateien Übersicht

| Datei | Tests | Bereich |
|-------|-------|---------|
| `test_libre_data.py` | 12 | Glucose-Daten speichern/lesen |
| `test_alarm_evaluator.py` | 21 | Alarm-Pipeline (Thresholds, Dispatch, Snooze) |
| `test_auth.py` | 17 | Login, Token, Berechtigungen |
| `test_notification_profiles.py` | 20 | Profile CRUD, Snooze, Webhook |
| `test_users_api.py` | 20 | User-Verwaltung mit Auth-Restrictions |
| `test_settings_api.py` | 19 | Thresholds, Passwort, Email, Settings |
| `test_log_api.py` | 12 | Log-Einträge, Basal-Rate, KE-Faktor |
| `test_leader_election.py` | 9 | Leader-Election (atomar) |
| `test_twilio_caller.py` | 8 | Twilio-Anrufe |
| `test_web_push.py` | 5 | Web-Push (VAPID) |
| `test_dashboard.py` | 8 | Dashboard (Current, History, Stats) |
| `test_shifts_night_family.py` | 10 | Schichten, Nachtprofil, Family-Dashboard |