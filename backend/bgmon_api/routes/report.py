"""Report API — generates AGP-style reports for the logged-in user."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from http import HTTPStatus

from flask import Blueprint, jsonify

from bgmon_api.auth_utils import get_current_user
from bgmon_api.extensions import db
from bgmon_api.models import GlucoseReading, LogEntry

report_bp = Blueprint("report", __name__)

MAX_REPORT_DAYS = 90


@report_bp.route("/api/report", methods=["GET"])
def generate_report():  # noqa: ANN201
    """Return AGP report data as JSON for the authenticated user.

    Query params:
        start: YYYY-MM-DD (default: 14 days ago)
        end:   YYYY-MM-DD (default: today)
    """
    from bgmon_api.services.report_service import compute_report_data  # noqa: PLC0415

    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    # Parse date range
    from flask import request  # noqa: PLC0415

    today = datetime.now(UTC).date()
    try:
        start_str = request.args.get("start")
        end_str = request.args.get("end")
        start_date = (
            datetime.fromisoformat(start_str).date()
            if start_str
            else today - timedelta(days=13)
        )
        end_date = datetime.fromisoformat(end_str).date() if end_str else today
    except ValueError:
        return jsonify({"error": "Ungültiges Datumsformat (YYYY-MM-DD)"}), HTTPStatus.BAD_REQUEST

    if start_date > end_date:
        return jsonify({"error": "Startdatum muss vor Enddatum liegen"}), HTTPStatus.BAD_REQUEST

    num_days = (end_date - start_date).days + 1
    if num_days > MAX_REPORT_DAYS:
        return jsonify({"error": f"Maximal {MAX_REPORT_DAYS} Tage"}), HTTPStatus.BAD_REQUEST

    # Convert to datetimes (full days, local midnight in UTC)
    start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=UTC)
    end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=UTC)

    # Fetch data
    readings = (
        db.session.query(GlucoseReading)
        .filter(GlucoseReading.timestamp >= start_dt)
        .filter(GlucoseReading.timestamp <= end_dt)
        .filter(GlucoseReading.sgv.isnot(None))
        .order_by(GlucoseReading.timestamp.asc())
        .all()
    )

    entries = (
        db.session.query(LogEntry)
        .filter(LogEntry.user_id == user.id)
        .filter(LogEntry.created_at >= start_dt)
        .filter(LogEntry.created_at <= end_dt)
        .order_by(LogEntry.created_at.asc())
        .all()
    )

    db.session.remove()

    report = compute_report_data(start_dt, end_dt, readings, entries)

    # Serialize to JSON-friendly dict
    from dataclasses import asdict  # noqa: PLC0415

    return jsonify(asdict(report))
