"""KE-estimator endpoint tests (POST /api/ai/estimate)."""

from http import HTTPStatus
from unittest.mock import patch

from bgmon_api.services.ke_estimator import KeEstimationError


def test_estimate_requires_input(client, patient_user, auth_headers):
    response = client.post(
        "/api/ai/estimate",
        json={},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.get_json() == {"error": "missing_input"}


def test_estimate_requires_auth(client):
    response = client.post("/api/ai/estimate", json={"meal_description": "Apfel"})

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_estimate_failure_does_not_leak_exception(client, patient_user, auth_headers):
    with patch(
        "bgmon_api.routes.ke_estimator.estimate_ke_from_description",
        side_effect=KeEstimationError("boom secret-detail"),
    ):
        response = client.post(
            "/api/ai/estimate",
            json={"meal_description": "Apfel"},
            headers=auth_headers(patient_user),
        )

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.get_json() == {"error": "llm_unavailable"}
    assert "secret-detail" not in response.get_data(as_text=True)


def test_estimate_success_returns_payload(client, patient_user, auth_headers):
    payload = {"ke_value": 2.5, "reasoning": "Apfel", "food_summary": "Apfel"}

    with patch(
        "bgmon_api.routes.ke_estimator.estimate_ke_from_description",
        return_value=payload,
    ):
        response = client.post(
            "/api/ai/estimate",
            json={"meal_description": "Apfel"},
            headers=auth_headers(patient_user),
        )

    assert response.status_code == HTTPStatus.OK
    assert response.get_json() == payload
