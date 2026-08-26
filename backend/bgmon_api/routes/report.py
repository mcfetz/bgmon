"""Report API that generates AGP-style reports for the configured patient."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from http import HTTPStatus
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from flask_limiter.util import get_remote_address

from bgmon_api.auth_utils import get_current_user
from bgmon_api.extensions import db, limiter
from bgmon_api.models import GlucoseReading, LogEntry, Session, User, UserRole

report_bp = Blueprint("report", __name__)

MAX_REPORT_DAYS = 90
# Libre data normally arrives no more frequently than once per minute. Reject
# abnormally dense imports instead of silently truncating a medical report or
# allowing one request to allocate an unbounded number of ORM objects.
MAX_REPORT_READINGS = 150_000
MAX_REPORT_LOG_ENTRIES = 10_000
LOCAL_TZ = ZoneInfo("Europe/Berlin")


def _report_rate_limit_key() -> str:
    """Rate-limit reports by authenticated user, with IP fallback before auth."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.removeprefix("Bearer ")
        session = Session.query.filter(
            Session.token == token, Session.expires_at > datetime.now(UTC)
        ).first()
        if session is not None:
            return f"user:{session.user_id}"
    return f"ip:{get_remote_address()}"


@report_bp.route("/api/report", methods=["GET"])
@limiter.limit("10 per minute", key_func=_report_rate_limit_key)
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
    if not user.is_active:
        return jsonify({"error": "account deactivated"}), HTTPStatus.UNAUTHORIZED

    # Parse date range
    now_local = datetime.now(LOCAL_TZ)
    today = now_local.date()
    try:
        start_str = request.args.get("start")
        end_str = request.args.get("end")
        start_date = _parse_report_date(start_str) if start_str else today - timedelta(days=13)
        end_date = _parse_report_date(end_str) if end_str else today
    except ValueError:
        return jsonify({"error": "Ungültiges Datumsformat (YYYY-MM-DD)"}), HTTPStatus.BAD_REQUEST

    if start_date > end_date:
        return jsonify({"error": "Startdatum muss vor Enddatum liegen"}), HTTPStatus.BAD_REQUEST

    # Validate before adding a day so YYYY-MM-DD date.max cannot overflow.
    if start_date > today or end_date > today:
        return jsonify({"error": "future_date_not_allowed"}), HTTPStatus.BAD_REQUEST

    num_days = (end_date - start_date).days + 1
    if num_days > MAX_REPORT_DAYS:
        return jsonify({"error": f"Maximal {MAX_REPORT_DAYS} Tage"}), HTTPStatus.BAD_REQUEST

    # Berlin local calendar dates map to a half-open UTC query interval.
    # At datetime.min, historical Berlin's positive local offset cannot be
    # represented in UTC; report a controlled validation error instead of 500.
    try:
        start_dt = datetime.combine(start_date, time.min, tzinfo=LOCAL_TZ).astimezone(
            ZoneInfo("UTC")
        )
        if end_date == today:
            effective_end_dt = now_local.astimezone(ZoneInfo("UTC"))
        else:
            calendar_end_exclusive_dt = datetime.combine(
                end_date + timedelta(days=1), time.min, tzinfo=LOCAL_TZ
            ).astimezone(ZoneInfo("UTC"))
            effective_end_dt = calendar_end_exclusive_dt
    except OverflowError:
        return jsonify({"error": "invalid_date_range"}), HTTPStatus.BAD_REQUEST

    # Reports always describe the patient, not the authenticated observer/admin.
    patients = User.query.filter_by(role=UserRole.PATIENT).order_by(User.id.asc()).limit(2).all()
    if not patients:
        return jsonify({"error": "no_patient"}), HTTPStatus.NOT_FOUND
    if len(patients) > 1:
        return (
            jsonify({"error": "multiple_patients", "message": "Report requires one patient"}),
            HTTPStatus.CONFLICT,
        )
    patient = patients[0]
    patient_name = patient.display_name

    # Glucose readings are global because the model has no patient foreign key.
    readings = (
        db.session.query(GlucoseReading)
        .filter(GlucoseReading.timestamp >= start_dt)
        .filter(GlucoseReading.timestamp < effective_end_dt)
        .filter(GlucoseReading.sgv.isnot(None))
        .order_by(GlucoseReading.timestamp.asc())
        .limit(MAX_REPORT_READINGS + 1)
        .all()
    )
    if len(readings) > MAX_REPORT_READINGS:
        return jsonify({"error": "report_data_limit_exceeded"}), HTTPStatus.BAD_REQUEST
    predecessor = (
        db.session.query(GlucoseReading)
        .filter(GlucoseReading.timestamp < start_dt)
        .filter(GlucoseReading.sgv.isnot(None))
        .order_by(GlucoseReading.timestamp.desc())
        .first()
    )

    entries = (
        db.session.query(LogEntry)
        .filter(LogEntry.user_id == patient.id)
        .filter(LogEntry.created_at >= start_dt)
        .filter(LogEntry.created_at < effective_end_dt)
        .order_by(LogEntry.created_at.asc())
        .limit(MAX_REPORT_LOG_ENTRIES + 1)
        .all()
    )
    if len(entries) > MAX_REPORT_LOG_ENTRIES:
        return jsonify({"error": "report_data_limit_exceeded"}), HTTPStatus.BAD_REQUEST

    report = compute_report_data(
        start_date,
        end_date,
        readings,
        entries,
        patient_name=patient_name,
        predecessor=predecessor,
        effective_end=effective_end_dt,
    )

    # Serialize to JSON-friendly dict
    from dataclasses import asdict  # noqa: PLC0415

    return jsonify(asdict(report))


def _parse_report_date(value: str) -> date:
    """Parse exactly one YYYY-MM-DD calendar date."""
    parsed = datetime.strptime(value, "%Y-%m-%d").date()
    if parsed.isoformat() != value:
        raise ValueError("date must use YYYY-MM-DD")
    return parsed
