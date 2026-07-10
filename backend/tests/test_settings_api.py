from http import HTTPStatus

import pytest

from bgmon_api.config import Config
from bgmon_api.models import User


def test_get_global_settings_returns_defaults(client, patient_user, auth_headers):
    response = client.get("/api/settings/global", headers=auth_headers(patient_user))

    assert response.status_code == HTTPStatus.OK
    assert response.get_json()["insulin_action_hours"] == 4.0
    assert response.get_json()["correction_factor"] == 50.0


def test_post_global_settings_by_non_patient_succeeds(
    client,
    observer_user,
    global_settings,
    auth_headers,
):
    response = client.post(
        "/api/settings/global",
        json={"insulin_action_hours": 5.0},
        headers=auth_headers(observer_user),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.get_json()["insulin_action_hours"] == 5.0
    assert response.get_json()["correction_factor"] == global_settings.correction_factor


def test_post_global_settings_by_patient_forbidden(client, patient_user, auth_headers):
    response = client.post(
        "/api/settings/global",
        json={"insulin_action_hours": 5.0},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.get_json() == {"error": "forbidden"}


def test_post_global_settings_with_invalid_insulin_action_hours(
    client,
    observer_user,
    auth_headers,
):
    response = client.post(
        "/api/settings/global",
        json={"insulin_action_hours": 0},
        headers=auth_headers(observer_user),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.get_json() == {"error": "insulin_action_hours must be positive number"}


def test_post_global_settings_with_valid_values(client, observer_user, auth_headers):
    response = client.post(
        "/api/settings/global",
        json={"insulin_action_hours": 6.5, "correction_factor": 42.0},
        headers=auth_headers(observer_user),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.get_json()["insulin_action_hours"] == 6.5
    assert response.get_json()["correction_factor"] == 42.0


def test_get_thresholds_returns_defaults(client, patient_user, auth_headers):
    response = client.get("/api/settings/thresholds", headers=auth_headers(patient_user))

    assert response.status_code == HTTPStatus.OK
    assert response.get_json() == {
        "critical_low": 54.0,
        "low": 70.0,
        "high": 180.0,
        "critical_high": 250.0,
    }


def test_post_thresholds_updates_low_value(client, patient_user, thresholds, auth_headers):
    response = client.post(
        "/api/settings/thresholds",
        json={"low": 68.0},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert data["critical_low"] == thresholds.critical_low
    assert data["low"] == 68.0


def test_post_thresholds_rejects_critical_low_greater_equal_low(
    client,
    patient_user,
    thresholds,
    auth_headers,
    db_session,
):
    response = client.post(
        "/api/settings/thresholds",
        json={"critical_low": thresholds.low},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.get_json() == {"error": "critical_low must be < low"}
    db_session.rollback()


def test_post_thresholds_negative_value_is_stored(client, patient_user, auth_headers):
    response = client.post(
        "/api/settings/thresholds",
        json={"critical_low": -10.0, "low": 60.0, "high": 180.0, "critical_high": 250.0},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.get_json()["critical_low"] == -10.0


def test_change_password_with_correct_current_password(
    client,
    patient_user,
    auth_headers,
    db_session,
):
    response = client.post(
        "/api/settings/password",
        json={"current_password": "test_password", "new_password": "betterpass"},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.get_json() == {"message": "password changed"}
    refreshed_user = db_session.get(User, patient_user.id)
    assert refreshed_user is not None
    assert refreshed_user.check_password("betterpass")


def test_change_password_with_wrong_current_password(client, patient_user, auth_headers):
    response = client.post(
        "/api/settings/password",
        json={"current_password": "wrong", "new_password": "betterpass"},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.get_json() == {"error": "current password incorrect"}


def test_change_password_with_too_short_new_password(client, patient_user, auth_headers):
    response = client.post(
        "/api/settings/password",
        json={"current_password": "test_password", "new_password": "short"},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.get_json() == {"error": "new password must be at least 6 characters"}


def test_update_email_success(client, patient_user, auth_headers):
    response = client.post(
        "/api/settings/email",
        json={"email": "updated.patient@example.com"},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.get_json() == {"email": "updated.patient@example.com"}


def test_update_email_with_invalid_format(client, patient_user, auth_headers):
    response = client.post(
        "/api/settings/email",
        json={"email": "invalid-email"},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.get_json() == {"error": "invalid email format"}


def test_update_email_to_already_taken_address(client, patient_user, observer_user, auth_headers):
    response = client.post(
        "/api/settings/email",
        json={"email": observer_user.email},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.get_json() == {"error": "email already in use"}


def test_get_twilio_numbers_returns_available_numbers(client, patient_user, auth_headers):
    response = client.get("/api/settings/twilio/numbers", headers=auth_headers(patient_user))

    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert data["numbers"] == Config.get_twilio_numbers()
    assert data["current"] == (patient_user.twilio_from_number or Config.TWILIO_FROM_NUMBER or "")


@pytest.mark.skipif(not Config.get_twilio_numbers(), reason="No Twilio numbers configured")
def test_post_twilio_settings_updates_from_number(client, observer_user, auth_headers, db_session):
    from_number = Config.get_twilio_numbers()[0]

    response = client.post(
        "/api/settings/twilio",
        json={"from_number": from_number},
        headers=auth_headers(observer_user),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.get_json()["from_number"] == from_number
    refreshed_user = db_session.get(User, observer_user.id)
    assert refreshed_user is not None
    assert refreshed_user.twilio_from_number == from_number


def test_post_twilio_settings_invalid_from_number(client, observer_user, auth_headers):
    response = client.post(
        "/api/settings/twilio",
        json={"from_number": "+19999999999"},
        headers=auth_headers(observer_user),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.get_json() == {"error": "number not in configured Twilio numbers"}


@pytest.mark.skipif(not Config.get_twilio_numbers(), reason="No Twilio numbers configured")
def test_post_twilio_settings_from_number_equals_phone_number(client, observer_user, auth_headers):
    conflicting_number = Config.get_twilio_numbers()[0]

    response = client.post(
        "/api/settings/twilio",
        json={"from_number": conflicting_number, "phone_number": conflicting_number},
        headers=auth_headers(observer_user),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.get_json() == {"error": "from_number and phone_number must differ"}
