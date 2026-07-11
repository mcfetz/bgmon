"""Tests for authentication: login, token validation, authorization checks."""

from http import HTTPStatus

from sqlalchemy.exc import SQLAlchemyError


class TestLogin:
    """Login, session, and logout behavior."""

    def test_login_valid_credentials(self, client, patient_user):
        """Accept valid credentials and create a session token."""
        _ = patient_user
        resp = client.post("/api/auth/login", json={
            "email": "patient@example.com",
            "password": "test_password",
        })
        assert resp.status_code == HTTPStatus.OK
        data = resp.get_json()
        assert "token" in data
        assert data["user"]["email"] == "patient@example.com"

    def test_login_invalid_password(self, client, patient_user):
        """Reject a valid user with the wrong password."""
        _ = patient_user
        resp = client.post("/api/auth/login", json={
            "email": "patient@example.com",
            "password": "wrong_password",
        })
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_login_nonexistent_user(self, client):
        """Reject credentials for a missing user."""
        resp = client.post("/api/auth/login", json={
            "email": "nobody@example.com",
            "password": "whatever",
        })
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_login_inactive_user(self, client, inactive_user):
        """Reject login for deactivated accounts."""
        _ = inactive_user
        resp = client.post("/api/auth/login", json={
            "email": "inactive@example.com",
            "password": "test_password",
        })
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_login_rate_limited(self, client, patient_user):
        """Block the first attempt beyond the configured per-minute threshold."""
        _ = patient_user
        for _ in range(10):
            resp = client.post("/api/auth/login", json={
                "email": "patient@example.com",
                "password": "wrong_password",
            })
            assert resp.status_code == HTTPStatus.UNAUTHORIZED
        resp = client.post("/api/auth/login", json={
            "email": "patient@example.com",
            "password": "test_password",
        })
        assert resp.status_code == HTTPStatus.TOO_MANY_REQUESTS

    def test_login_rate_limit_boundary_allows_tenth_attempt(self, client, patient_user):
        """Allow the tenth attempt and block only the one after the threshold."""
        _ = patient_user
        for _ in range(9):
            resp = client.post("/api/auth/login", json={
                "email": "patient@example.com",
                "password": "wrong_password",
            })
            assert resp.status_code == HTTPStatus.UNAUTHORIZED

        resp = client.post("/api/auth/login", json={
            "email": "patient@example.com",
            "password": "test_password",
        })
        assert resp.status_code == HTTPStatus.OK

    def test_me_with_valid_token(self, client, patient_user):
        """Return the authenticated user for a valid bearer token."""
        resp = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.OK
        assert resp.get_json()["email"] == "patient@example.com"

    def test_me_without_token(self, client):
        """Reject missing bearer tokens."""
        resp = client.get("/api/auth/me")
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_me_with_invalid_token(self, client):
        """Reject invalid bearer tokens."""
        resp = client.get("/api/auth/me", headers={
            "Authorization": "Bearer invalid-token",
        })
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_logout(self, client, patient_user):
        """Invalidate a valid session token on logout."""
        token = patient_user._session.token
        resp = client.post("/api/auth/logout", headers={
            "Authorization": f"Bearer {token}",
        })
        assert resp.status_code == HTTPStatus.OK
        resp2 = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert resp2.status_code == HTTPStatus.UNAUTHORIZED

    def test_logout_without_token(self, client):
        """Treat logout without a token as a no-op."""
        resp = client.post("/api/auth/logout")
        assert resp.status_code == HTTPStatus.OK
        assert resp.get_json() == {"status": "ok"}

    def test_logout_with_invalid_token(self, client):
        """Treat logout with an unknown token as a no-op."""
        resp = client.post("/api/auth/logout", headers={
            "Authorization": "Bearer invalid-token",
        })
        assert resp.status_code == HTTPStatus.OK
        assert resp.get_json() == {"status": "ok"}

    def test_logout_db_failure(self, client, monkeypatch, patient_user):
        """Return 500 when session revocation fails in the database."""
        from bgmon_api.extensions import db

        def raise_delete_error(_session):
            raise SQLAlchemyError("db unavailable")

        monkeypatch.setattr(db.session, "delete", raise_delete_error)

        token = patient_user._session.token
        resp = client.post("/api/auth/logout", headers={
            "Authorization": f"Bearer {token}",
        })

        assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert resp.get_json() == {"error": "Failed to revoke session"}

        still_valid = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert still_valid.status_code == HTTPStatus.OK


class TestAuthorization:
    """Authorization behavior for user and admin endpoints."""

    def test_patient_cannot_list_users(self, client, patient_user):
        """Prevent patient users from listing all users."""
        resp = client.get("/api/users", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_observer_cannot_list_users(self, client, observer_user):
        """Prevent observer users from listing all users."""
        resp = client.get("/api/users", headers={
            "Authorization": f"Bearer {observer_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_admin_can_list_users(self, client, admin_user):
        """Allow admins to list all users."""
        resp = client.get("/api/users", headers={
            "Authorization": f"Bearer {admin_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.OK
        assert isinstance(resp.get_json(), list)

    def test_user_can_see_own_data(self, client, patient_user):
        """Allow a user to fetch their own profile."""
        resp = client.get(f"/api/users/{patient_user.id}", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.OK
        assert resp.get_json()["email"] == "patient@example.com"

    def test_observer_cannot_see_other_user(self, client, observer_user, patient_user):
        """Prevent observers from reading another user's profile."""
        resp = client.get(f"/api/users/{patient_user.id}", headers={
            "Authorization": f"Bearer {observer_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_patient_cannot_see_other_thresholds(self, client, patient_user, observer_user):
        """Prevent patients from reading another user's thresholds."""
        resp = client.get(f"/api/users/{observer_user.id}/thresholds", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_owner_can_see_own_thresholds(self, client, patient_user, thresholds):
        """Allow a user to read their own thresholds."""
        _ = thresholds
        resp = client.get(f"/api/users/{patient_user.id}/thresholds", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.OK
        assert resp.get_json()["low"] == 70.0

    def test_patient_cannot_see_other_snooze_presets(self, client, patient_user, observer_user):
        """Prevent patients from reading another user's snooze presets."""
        resp = client.get(f"/api/users/{observer_user.id}/snooze-presets", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.FORBIDDEN
