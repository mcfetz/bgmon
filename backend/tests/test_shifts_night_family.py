from __future__ import annotations

from datetime import UTC, datetime, timedelta
from http import HTTPStatus

from bgmon_api.models import GlucoseReading, Shift


def test_start_shift(client, observer_user, auth_headers):
    response = client.post(
        "/api/shifts/start",
        headers=auth_headers(observer_user),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.get_json()["status"] == "started"

    active_response = client.get(
        "/api/shifts/active",
        headers=auth_headers(observer_user),
    )

    active_data = active_response.get_json()

    assert active_response.status_code == HTTPStatus.OK
    assert active_data["active"] is True
    assert active_data["shift"]["user_id"] == observer_user.id


def test_patient_cannot_start_shift(client, patient_user, auth_headers):
    response = client.post(
        "/api/shifts/start",
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.get_json() == {"error": "patient cannot take shift"}


def test_end_shift(client, observer_user, auth_headers):
    start_response = client.post(
        "/api/shifts/start",
        headers=auth_headers(observer_user),
    )
    shift_id = start_response.get_json()["shift_id"]

    response = client.post(
        "/api/shifts/end",
        headers=auth_headers(observer_user),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.get_json() == {"status": "ended"}

    active_response = client.get(
        "/api/shifts/active",
        headers=auth_headers(observer_user),
    )
    history_response = client.get(
        "/api/shifts/history",
        headers=auth_headers(observer_user),
    )

    assert active_response.get_json() == {"active": False, "shift": None}
    assert history_response.get_json()["shifts"][0]["id"] == shift_id
    assert history_response.get_json()["shifts"][0]["active"] is False
    assert history_response.get_json()["shifts"][0]["ended_at"] is not None


def test_start_auto_ends_previous(client, db_session, observer_user, admin_user, auth_headers):
    first_start = client.post(
        "/api/shifts/start",
        headers=auth_headers(observer_user),
    )
    first_shift_id = first_start.get_json()["shift_id"]

    second_start = client.post(
        "/api/shifts/start",
        headers=auth_headers(admin_user),
    )
    second_shift_id = second_start.get_json()["shift_id"]

    first_shift = db_session.get(Shift, first_shift_id)
    second_shift = db_session.get(Shift, second_shift_id)

    assert second_start.status_code == HTTPStatus.OK
    assert first_shift is not None
    assert second_shift is not None
    assert first_shift.active is False
    assert first_shift.ended_at is not None
    assert second_shift.active is True
    assert second_shift.user_id == admin_user.id


def test_shift_history(client, observer_user, auth_headers):
    client.post(
        "/api/shifts/start",
        headers=auth_headers(observer_user),
    )
    client.post(
        "/api/shifts/end",
        headers=auth_headers(observer_user),
    )

    response = client.get(
        "/api/shifts/history",
        headers=auth_headers(observer_user),
    )

    data = response.get_json()

    assert response.status_code == HTTPStatus.OK
    assert isinstance(data["shifts"], list)
    assert len(data["shifts"]) == 1
    assert data["shifts"][0]["active"] is False


def test_get_night_profile(client, patient_user, auth_headers):
    response = client.get(
        "/api/night/profile",
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.get_json()["enabled"] is False
    assert response.get_json()["start_time"] == "22:30"
    assert response.get_json()["end_time"] == "06:30"


def test_update_night_profile(client, patient_user, night_profile, auth_headers):
    response = client.post(
        "/api/night/profile",
        json={"enabled": False, "start_time": "21:15", "end_time": "05:45"},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.get_json()["enabled"] is False
    assert response.get_json()["start_time"] == "21:15"
    assert response.get_json()["end_time"] == "05:45"


def test_family_dashboard_with_token(client, family_token, glucose_reading_normal):
    response = client.get(f"/api/family/{family_token.token}")

    data = response.get_json()

    assert response.status_code == HTTPStatus.OK
    assert data["token_valid"] is True
    assert data["current"]["sgv"] == glucose_reading_normal.sgv
    assert "stats" in data


def test_family_dashboard_invalid_token(client):
    response = client.get("/api/family/invalid-token")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.get_json() == {"error": "invalid token"}


def test_family_current_glucose(client, db_session, family_token):
    earlier = GlucoseReading()
    earlier.timestamp = datetime.now(UTC) - timedelta(minutes=15)
    earlier.sgv = 111
    earlier.trend = 2
    earlier.direction = "Flat"
    earlier.source = "test"

    latest = GlucoseReading()
    latest.timestamp = datetime.now(UTC) - timedelta(minutes=1)
    latest.sgv = 144
    latest.trend = 4
    latest.direction = "SingleUp"
    latest.source = "test"

    db_session.add(earlier)
    db_session.add(latest)
    db_session.commit()

    response = client.get(f"/api/family/{family_token.token}/current")

    assert response.status_code == HTTPStatus.OK
    assert response.get_json()["sgv"] == 144
    assert response.get_json()["direction"] == "SingleUp"
