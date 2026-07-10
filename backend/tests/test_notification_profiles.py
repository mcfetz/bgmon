"""Tests for notification profiles: CRUD, active profile, assignments, routing."""

from http import HTTPStatus

import pytest


class TestProfileCRUD:
    def test_create_profile(self, client, patient_user):
        resp = client.post("/api/notifications/profiles", json={
            "name": "Test Profile",
            "icon": "bell",
            "assignments": [
                {"area": "push", "threshold": "critical_low"},
                {"area": "push", "threshold": "low"},
                {"area": "call", "threshold": "high"},
                {"area": "call", "threshold": "critical_high"},
            ],
        }, headers={"Authorization": f"Bearer {patient_user._session.token}"})
        assert resp.status_code == HTTPStatus.CREATED
        data = resp.get_json()
        assert data["name"] == "Test Profile"
        assert len(data["assignments"]) == 4

    def test_create_profile_no_name(self, client, patient_user):
        resp = client.post("/api/notifications/profiles", json={}, headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.BAD_REQUEST

    def test_create_profile_invalid_area(self, client, patient_user):
        resp = client.post("/api/notifications/profiles", json={
            "name": "Bad",
            "assignments": [{"area": "sms", "threshold": "low"}],
        }, headers={"Authorization": f"Bearer {patient_user._session.token}"})
        assert resp.status_code == HTTPStatus.BAD_REQUEST

    def test_create_profile_invalid_threshold(self, client, patient_user):
        resp = client.post("/api/notifications/profiles", json={
            "name": "Bad",
            "assignments": [{"area": "push", "threshold": "medium"}],
        }, headers={"Authorization": f"Bearer {patient_user._session.token}"})
        assert resp.status_code == HTTPStatus.BAD_REQUEST

    def test_create_profile_duplicate_threshold(self, client, patient_user):
        resp = client.post("/api/notifications/profiles", json={
            "name": "Bad",
            "assignments": [
                {"area": "push", "threshold": "low"},
                {"area": "call", "threshold": "low"},
            ],
        }, headers={"Authorization": f"Bearer {patient_user._session.token}"})
        assert resp.status_code == HTTPStatus.BAD_REQUEST

    def test_list_profiles(self, client, patient_user, notification_profile_with_assignments):
        resp = client.get("/api/notifications/profiles", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.OK
        assert len(resp.get_json()) >= 1

    def test_list_profiles_empty(self, client, patient_user):
        resp = client.get("/api/notifications/profiles", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.OK
        assert resp.get_json() == []

    def test_update_profile(self, client, patient_user, notification_profile_with_assignments):
        pid = notification_profile_with_assignments.id
        resp = client.patch(f"/api/notifications/profiles/{pid}", json={
            "name": "Updated",
        }, headers={"Authorization": f"Bearer {patient_user._session.token}"})
        assert resp.status_code == HTTPStatus.OK
        assert resp.get_json()["name"] == "Updated"

    def test_delete_profile(self, client, patient_user, notification_profile_with_assignments):
        pid = notification_profile_with_assignments.id
        resp = client.delete(f"/api/notifications/profiles/{pid}", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.OK
        resp2 = client.get("/api/notifications/profiles", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert len(resp2.get_json()) == 0

    def test_delete_nonexistent_profile(self, client, patient_user):
        resp = client.delete("/api/notifications/profiles/9999", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_cannot_delete_other_users_profile(self, client, patient_user, observer_user, notification_profile_with_assignments):
        resp = client.delete(f"/api/notifications/profiles/{notification_profile_with_assignments.id}", headers={
            "Authorization": f"Bearer {observer_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.NOT_FOUND


class TestActiveProfile:
    def test_get_active_profile(self, client, patient_user, notification_profile_with_assignments):
        resp = client.get("/api/notifications/active", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.OK
        data = resp.get_json()
        assert data["profile_id"] == notification_profile_with_assignments.id

    def test_get_active_profile_none(self, client, patient_user):
        resp = client.get("/api/notifications/active", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.OK
        assert resp.get_json()["profile_id"] is None

    def test_set_active_profile(self, client, patient_user, notification_profile_with_assignments):
        resp = client.put("/api/notifications/active", json={
            "profile_id": notification_profile_with_assignments.id,
        }, headers={"Authorization": f"Bearer {patient_user._session.token}"})
        assert resp.status_code == HTTPStatus.OK

    def test_set_active_profile_not_found(self, client, patient_user):
        resp = client.put("/api/notifications/active", json={
            "profile_id": 9999,
        }, headers={"Authorization": f"Bearer {patient_user._session.token}"})
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_webhook_activate_profile(self, client, notification_profile_with_assignments):
        resp = client.get(f"/api/notifications/active/{notification_profile_with_assignments.id}")
        assert resp.status_code == HTTPStatus.OK


class TestSnooze:
    def test_set_snooze(self, client, patient_user):
        resp = client.post("/api/notifications/snooze", json={
            "minutes": 15,
            "reason": "testing",
        }, headers={"Authorization": f"Bearer {patient_user._session.token}"})
        assert resp.status_code == HTTPStatus.OK
        assert resp.get_json()["active"] is True

    def test_get_snooze(self, client, patient_user):
        client.post("/api/notifications/snooze", json={"minutes": 15}, headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        resp = client.get("/api/notifications/snooze", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.OK
        assert resp.get_json()["active"] is True

    def test_clear_snooze(self, client, patient_user):
        client.post("/api/notifications/snooze", json={"minutes": 15}, headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        resp = client.delete("/api/notifications/snooze", headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        assert resp.status_code == HTTPStatus.OK

    def test_adjust_snooze(self, client, patient_user):
        client.post("/api/notifications/snooze", json={"minutes": 15}, headers={
            "Authorization": f"Bearer {patient_user._session.token}",
        })
        resp = client.patch("/api/notifications/snooze", json={
            "delta_minutes": 10,
        }, headers={"Authorization": f"Bearer {patient_user._session.token}"})
        assert resp.status_code == HTTPStatus.OK
