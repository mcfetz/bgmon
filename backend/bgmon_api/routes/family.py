"""Family dashboard — read-only access via secret token URL.

Primary storage: PostgreSQL (GlucoseReading model).
"""

from http import HTTPStatus

from flask import Blueprint, jsonify
from flask import Response as FlaskResponse

from bgmon_api.models import FamilyDashboardToken, GlucoseReading

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
    if not values:
        stats = {
            "mean": None,
            "tir_percent": None,
            "tir_below": None,
            "tir_above": None,
            "gmi": None,
            "std_dev": None,
            "readings": 0,
            "min": None,
            "max": None,
        }
    else:
        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        std_dev = variance**0.5
        gmi = 46.7 + mean / 1.594
        tir_below = sum(1 for v in values if v < 70)
        tir_above = sum(1 for v in values if v > 180)
        tir_in_range = n - tir_below - tir_above
        stats = {
            "mean": round(mean, 1),
            "tir_percent": round(tir_in_range / n * 100, 1),
            "tir_below": round(tir_below / n * 100, 1),
            "tir_above": round(tir_above / n * 100, 1),
            "gmi": round(gmi, 1),
            "std_dev": round(std_dev, 1),
            "readings": n,
            "min": min(values),
            "max": max(values),
        }

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
