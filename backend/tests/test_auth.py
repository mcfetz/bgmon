"""Tests for authentication: login, token validation, authorization checks."""

from http import HTTPStatus

import pytest


class TestLogin:
    def test_login_valid_credentials(self, client, patient_user):
        resp = client.post("/api/auth/login", json={
            "email": "patient@example.com",
            "password": "test_password",
        })
        assert resp.status_code == HTTPStatus.OK
        data = resp.get_json()
        assert "token" in data
        assert data["user"]["email"] == "patient@example.com"

    def test_login_invalid_password(self, client, patient_user):
        resp = client.post("/api/auth/login", json={
            "email": "patient@example.com",
            "password": "wrong_password",
        })
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/auth/login", json={
            "email": "nobody@example.com",
            "password": "whatever",
        })
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_login_inactive_user(self, client, inactive_user):
        resp = client.post("/api/auth/login", json={
            "email": "inactive@example.com",
            "password": "test_password",
        })
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    @pytest.mark.xfail(reason="rate limiting not yet implemented on login endpoint")
    def test_login_rate_limited(self, client, patient_user):
        for _ in range(12):
            client.post("/api/auth/login", json={
                "email": "patient@example.com",
                "password": "wrong_password",
            })
        resp = client.post("/api/auth/login", json={
            "email": "patient@example.com",
            "password": "test_password",
        })
        assert resp.status_code == HTTPStatus.TOO_MANY_REQUESTS

    def test_me_with_valid_token(self, client, patient_user):
        resp = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.OK
        assert resp.get_json()["email"] == "patient@example.com"

    def test_me_without_token(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_me_with_invalid_token(self, client):
        resp = client.get("/api/auth/me", headers={
            "Authorization": "Bearer invalid-token",
        })
        assert resp.status_code == HTTPStatus.UNAUTHORIZED

    def test_logout(self, client, patient_user):
        token = patient_user._session.token
        resp = client.post("/api/auth/logout", headers={
            "Authorization": f"Bearer {token}",
        })
        assert resp.status_code == HTTPStatus.OK
        resp2 = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert resp2.status_code == HTTPStatus.UNAUTHORIZED


class TestAuthorization:
    def test_patient_cannot_list_users(self, client, patient_user):
        resp = client.get("/api/users", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_observer_cannot_list_users(self, client, observer_user):
        resp = client.get("/api/users", headers={
            "Authorization": f"Bearer {observer_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_admin_can_list_users(self, client, admin_user):
        resp = client.get("/api/users", headers={
            "Authorization": f"Bearer {admin_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.OK
        assert isinstance(resp.get_json(), list)

    def test_user_can_see_own_data(self, client, patient_user):
        resp = client.get(f"/api/users/{patient_user.id}", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.OK
        assert resp.get_json()["email"] == "patient@example.com"

    def test_observer_cannot_see_other_user(self, client, observer_user, patient_user):
        resp = client.get(f"/api/users/{patient_user.id}", headers={
            "Authorization": f"Bearer {observer_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_patient_cannot_see_other_thresholds(self, client, patient_user, observer_user):
        resp = client.get(f"/api/users/{observer_user.id}/thresholds", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_owner_can_see_own_thresholds(self, client, patient_user, thresholds):
        resp = client.get(f"/api/users/{patient_user.id}/thresholds", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.OK
        assert resp.get_json()["low"] == 70.0

    def test_patient_cannot_see_other_snooze_presets(self, client, patient_user, observer_user):
        resp = client.get(f"/api/users/{observer_user.id}/snooze-presets", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.FORBIDDEN
