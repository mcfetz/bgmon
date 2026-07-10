"""PRIO-2 Tests: Authentication and API endpoints."""

from http import HTTPStatus


class TestAuthenticationEndpoints:
    """Test login, logout, and session management."""

    def test_login_with_valid_credentials(self, client, patient_user):
        """Test successful login with correct email and password."""
        response = client.post(
            "/api/auth/login",
            json={"email": "patient@example.com", "password": "test_password"},
        )
        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert "token" in data
        assert data["user"]["email"] == "patient@example.com"
        assert data["user"]["role"] == "patient"

    def test_login_with_invalid_password(self, client, patient_user):
        """Test login failure with wrong password."""
        response = client.post(
            "/api/auth/login",
            json={"email": "patient@example.com", "password": "wrong_password"},
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        data = response.get_json()
        assert "error" in data

    def test_login_with_nonexistent_user(self, client):
        """Test login failure with non-existent email."""
        response = client.post(
            "/api/auth/login",
            json={"email": "nonexistent@example.com", "password": "password"},
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_get_current_user_authenticated(self, client, patient_session):
        """Test /me endpoint returns current user when authenticated."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {patient_session.token}"},
        )
        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert data["email"] == "patient@example.com"
        assert data["display_name"] == "Test Patient"

    def test_get_current_user_unauthenticated(self, client):
        """Test /me endpoint returns 401 when not authenticated."""
        response = client.get("/api/auth/me")
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_logout_invalidates_session(self, client, patient_session):
        """Test that logout invalidates the session token."""
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {patient_session.token}"},
        )
        assert response.status_code == HTTPStatus.OK

        # Subsequent request with same token should fail
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {patient_session.token}"},
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED


class TestDashboardEndpoints:
    """Test glucose data and dashboard endpoints."""

    def test_get_current_glucose_reading(self, client, patient_session, db_session, app):
        """Test /dashboard/current returns latest glucose reading."""
        from datetime import UTC, datetime

        from bgmon_api.models import GlucoseReading

        with app.app_context():
            reading = GlucoseReading(
                sgv=125,
                trend="Flat",
                direction="Stable",
                timestamp=datetime.now(UTC),
            )
            db_session.add(reading)
            db_session.commit()

        response = client.get(
            "/api/dashboard/current",
            headers={"Authorization": f"Bearer {patient_session.token}"},
        )
        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert data["sgv"] == 125
        assert data["trend"] == "Flat"

    def test_get_glucose_history(self, client, patient_session, db_session, app):
        """Test /dashboard/history returns glucose readings in time range."""
        from datetime import UTC, datetime, timedelta

        from bgmon_api.models import GlucoseReading

        with app.app_context():
            now = datetime.now(UTC)
            for i in range(5):
                reading = GlucoseReading(
                    sgv=100 + i * 10,
                    trend="Flat",
                    direction="Stable",
                    timestamp=now - timedelta(hours=i),
                )
                db_session.add(reading)
            db_session.commit()

        response = client.get(
            "/api/dashboard/history?start=2020-01-01T00:00:00Z&end=2050-01-01T00:00:00Z",
            headers={"Authorization": f"Bearer {patient_session.token}"},
        )
        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert len(data) >= 5

    def test_get_thresholds(self, client, patient_session, thresholds):
        """Test /dashboard/thresholds returns user's thresholds."""
        response = client.get(
            "/api/dashboard/thresholds",
            headers={"Authorization": f"Bearer {patient_session.token}"},
        )
        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert data["critical_low"] == 54.0
        assert data["low"] == 70.0
        assert data["high"] == 180.0
        assert data["critical_high"] == 250.0


class TestLogEndpoints:
    """Test log entry creation and retrieval."""

    def test_create_log_entry(self, client, patient_session, db_session, app):
        """Test creating a log entry (carbs, insulin, etc)."""
        response = client.post(
            "/api/log/",
            json={
                "entry_type": "carbs",
                "value": 30,
                "unit": "g",
                "notes": "Bread and butter",
            },
            headers={"Authorization": f"Bearer {patient_session.token}"},
        )
        assert response.status_code == HTTPStatus.OK or response.status_code == HTTPStatus.CREATED
        data = response.get_json()
        assert data["entry_type"] == "carbs"
        assert data["value"] == 30

    def test_get_log_entries(self, client, patient_session, db_session, app):
        """Test retrieving log entries for current user."""
        from bgmon_api.models import LogEntry, LogEntryType

        with app.app_context():
            entry = LogEntry(
                user_id=patient_session.user_id,
                entry_type=LogEntryType.CARBS,
                value=25,
                unit="g",
                notes="Banana",
            )
            db_session.add(entry)
            db_session.commit()

        response = client.get(
            "/api/log/",
            headers={"Authorization": f"Bearer {patient_session.token}"},
        )
        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "entry_type" in data[0]
            assert "value" in data[0]


class TestSettingsEndpoints:
    """Test settings endpoints."""

    def test_get_global_settings(self, client, patient_session):
        """Test retrieving global settings."""
        response = client.get(
            "/api/settings/global",
            headers={"Authorization": f"Bearer {patient_session.token}"},
        )
        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert "insulin_action_hours" in data
        assert "correction_factor" in data

    def test_update_thresholds(self, client, patient_session, thresholds):
        """Test updating glucose thresholds."""
        response = client.post(
            "/api/settings/thresholds",
            json={
                "critical_low": 50,
                "low": 65,
                "high": 185,
                "critical_high": 260,
            },
            headers={"Authorization": f"Bearer {patient_session.token}"},
        )
        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert data["critical_low"] == 50
        assert data["low"] == 65


class TestNotificationEndpoints:
    """Test notification profile endpoints."""

    def test_get_notification_profiles(
        self, client, patient_session, notification_profile_with_assignments
    ):
        """Test getting all notification profiles for user."""
        response = client.get(
            "/api/notifications/profiles",
            headers={"Authorization": f"Bearer {patient_session.token}"},
        )
        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert isinstance(data, list)

    def test_get_active_notification_profile(
        self, client, patient_session, notification_profile_with_assignments
    ):
        """Test getting active notification profile."""
        response = client.get(
            "/api/notifications/active",
            headers={"Authorization": f"Bearer {patient_session.token}"},
        )
        assert response.status_code == HTTPStatus.OK or response.status_code == HTTPStatus.NOT_FOUND
        if response.status_code == HTTPStatus.OK:
            data = response.get_json()
            assert "profile_id" in data or "id" in data


class TestAlarmEndpoints:
    """Test alarm-related endpoints."""

    def test_get_alarm_history(self, client, patient_session, db_session, app):
        """Test retrieving alarm history."""
        from bgmon_api.models import Alarm, AlarmType

        with app.app_context():
            alarm = Alarm(
                user_id=patient_session.user_id,
                alarm_type=AlarmType.LOW,
                sgv=65,
            )
            db_session.add(alarm)
            db_session.commit()

        response = client.get(
            "/api/alarms/",
            headers={"Authorization": f"Bearer {patient_session.token}"},
        )
        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert isinstance(data, list)

    def test_snooze_alarm(self, client, patient_session):
        """Test snoozing alarms."""
        response = client.post(
            "/api/alarms/snooze",
            json={"duration_minutes": 15},
            headers={"Authorization": f"Bearer {patient_session.token}"},
        )
        assert response.status_code == HTTPStatus.OK or response.status_code == HTTPStatus.CREATED

    def test_get_snooze_status(self, client, patient_session):
        """Test getting current snooze status."""
        response = client.get(
            "/api/alarms/snooze",
            headers={"Authorization": f"Bearer {patient_session.token}"},
        )
        assert response.status_code in [HTTPStatus.OK, HTTPStatus.NOT_FOUND]


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_endpoint_returns_ok(self, client):
        """Test /health returns ok status."""
        response = client.get("/health")
        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert data["status"] == "ok"
        assert "is_leader" in data
        assert "instance_id" in data
        assert "last_libre_fetch_at" in data
