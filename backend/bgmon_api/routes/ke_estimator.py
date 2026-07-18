"""KE-estimation blueprint — POST /api/ai/estimate.

Auth-gated endpoint that forwards a free-text meal description to the
OpenAI-compatible LLM configured by ``BGMON_LLM_*`` env vars and returns
a structured ``{ke_value, reasoning}`` payload.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from flask import Blueprint, jsonify, request
from flask import Response as FlaskResponse

from bgmon_api.auth_utils import get_current_user
from bgmon_api.services.ke_estimator import KeEstimationError, estimate_ke_from_description

ke_estimator_bp = Blueprint("ke_estimator", __name__)


@ke_estimator_bp.route("/estimate", methods=["POST"])
def estimate_ke() -> tuple[FlaskResponse, HTTPStatus] | FlaskResponse:
    """Estimate Kohlenhydrateinheiten for a meal description.

    Request body (JSON): ``{"meal_description": "<text>"}``
    Response: ``{"ke_value": <float>, "reasoning": "<text>"}``
    Errors:
        - 400 ``missing_meal_description`` — body absent or empty
        - 401 ``unauthorized`` — no valid session
        - 503 ``llm_unavailable`` — LLM call failed or returned garbage
    """
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "missing_meal_description"}), HTTPStatus.BAD_REQUEST

    raw_description = payload.get("meal_description")
    if not isinstance(raw_description, str) or not raw_description.strip():
        return jsonify({"error": "missing_meal_description"}), HTTPStatus.BAD_REQUEST

    try:
        result: dict[str, Any] = estimate_ke_from_description(raw_description)
    except KeEstimationError as exc:
        return (
            jsonify({"error": "llm_unavailable", "detail": str(exc)}),
            HTTPStatus.SERVICE_UNAVAILABLE,
        )

    return jsonify(result)
