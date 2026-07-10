"""Family dashboard — read-only access via secret token URL.

Primary storage: PostgreSQL (GlucoseReading model).
"""

from http import HTTPStatus

from flask import Blueprint, jsonify
from flask import Response as FlaskResponse

from bgmon_api.models import FamilyDashboardToken, GlucoseReading
from bgmon_api.utils import compute_glucose_stats

family_bp = Blueprint("family", __name__)


def _verify_token(token: str) -> FamilyDashboardToken | None:
    return FamilyDashboardToken.query.filter_by(token=token).first()


@family_bp.route("/<token>", methods=["GET"])
def dashboard(token: str) -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    entry = _verify_token(token)
    if not entry:
        return jsonify({"error": "invalid token"}), HTTPStatus.NOT_FOUND

    current = (
        GlucoseReading.query
        .order_by(GlucoseReading.timestamp.desc())
        .first()
    )
    current_data = {
        "sgv": current.sgv if current else None,
        "trend": current.trend if current else None,
        "direction": current.direction if current else None,
        "timestamp": current.timestamp.isoformat() if current and current.timestamp else None,
    }

    from datetime import UTC, datetime, timedelta
    since = datetime.now(UTC) - timedelta(hours=24)
    readings = (
        GlucoseReading.query
        .filter(GlucoseReading.timestamp >= since)
        .order_by(GlucoseReading.timestamp.asc())
        .all()
    )
    values = [r.sgv for r in readings if r.sgv is not None]
    stats = compute_glucose_stats(values)

    return jsonify({
        "current": current_data,
        "stats": stats,
        "token_valid": True,
    })


@family_bp.route("/<token>/current", methods=["GET"])
def current_glucose(token: str) -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    entry = _verify_token(token)
    if not entry:
        return jsonify({"error": "invalid token"}), HTTPStatus.NOT_FOUND

    current = (
        GlucoseReading.query
        .order_by(GlucoseReading.timestamp.desc())
        .first()
    )
    return jsonify({
        "sgv": current.sgv if current else None,
        "trend": current.trend if current else None,
        "direction": current.direction if current else None,
        "timestamp": current.timestamp.isoformat() if current and current.timestamp else None,
    })
