"""Patient logging blueprint — carbs, insulin, basal + history."""
import contextlib
from http import HTTPStatus
from math import isfinite

from flask import Blueprint, jsonify, request
from flask import Response as FlaskResponse

from bgmon_api.auth_utils import get_current_user
from bgmon_api.extensions import db
from bgmon_api.models import (
    MAX_LOG_ENTRY_NOTE_CHARS,
    MAX_LOG_ENTRY_VALUE,
    BasalRateHistory,
    CarbFactorHistory,
    LogEntry,
    LogEntryType,
    User,
    UserRole,
)
from bgmon_api.utils import parse_iso_datetime, transactional_session

log_bp = Blueprint("log", __name__)


@log_bp.route("/", methods=["GET"])
def list_logs() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    patient = _get_patient(user)
    if not patient:
        return jsonify({"error": "no patient found"}), HTTPStatus.NOT_FOUND

    query = LogEntry.query.filter_by(user_id=patient.id)

    start = request.args.get("start")
    end = request.args.get("end")
    if start:
        with contextlib.suppress(ValueError):
            query = query.filter(
                LogEntry.created_at >= parse_iso_datetime(start)
            )
    if end:
        with contextlib.suppress(ValueError):
            query = query.filter(
                LogEntry.created_at <= parse_iso_datetime(end)
            )

    logs = query.order_by(LogEntry.created_at.desc()).all()
    return jsonify([log.to_dict() for log in logs])


@log_bp.route("/<int:entry_id>", methods=["DELETE"])
def delete_log(entry_id: int) -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    entry = LogEntry.query.get_or_404(entry_id)
    db.session.delete(entry)
    with transactional_session():
        pass  # commit handled by context manager
    return jsonify({"deleted": True}), HTTPStatus.OK


EDITABLE_ENTRY_TYPES = frozenset(
    {
        LogEntryType.CARBS,
        LogEntryType.INSULIN,
        LogEntryType.BASAL,
        LogEntryType.NOTE,
    }
)

AUTO_NOTE_PREFIXES = (
    "SmartAlert:",
    "Kompressionstiefwert",
    "Basalrate von",
    "Basalrate auf",
    "KE-Faktor von",
    "KE-Faktor auf",
    "🤖 ML-Training",
    "Badge freigeschaltet",
    "Neuer Rekord-Streak",
    "Testanruf",
)


def _is_auto_note(entry: LogEntry) -> bool:
    """True for notes the system writes itself (alerts, settings, training)."""
    notes = entry.notes or ""
    return any(notes.startswith(prefix) for prefix in AUTO_NOTE_PREFIXES)


def _edit_block_reason(entry: LogEntry, patient: User) -> str | None:
    if entry.user_id != patient.id:
        return "entry belongs to another patient"
    if entry.entry_type not in EDITABLE_ENTRY_TYPES:
        return "this entry type cannot be edited"
    if entry.entry_type == LogEntryType.NOTE and _is_auto_note(entry):
        return "system notes cannot be edited"
    return None


@log_bp.route("/<int:entry_id>", methods=["PATCH"])
def update_log(entry_id: int) -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    patient = _get_patient(user)
    if not patient:
        return jsonify({"error": "no patient found"}), HTTPStatus.NOT_FOUND

    entry = LogEntry.query.get_or_404(entry_id)
    reason = _edit_block_reason(entry, patient)
    if reason is not None:
        status = (
            HTTPStatus.FORBIDDEN
            if reason == "entry belongs to another patient"
            else HTTPStatus.BAD_REQUEST
        )
        return jsonify({"error": reason}), status

    data = request.get_json(silent=True) or {}

    if "entry_type" in data and data["entry_type"] != entry.entry_type.value:
        return (
            jsonify({"error": "entry_type cannot be changed"}),
            HTTPStatus.BAD_REQUEST,
        )

    if "value" in data and entry.entry_type != LogEntryType.NOTE:
        try:
            value = float(data["value"])
        except (TypeError, ValueError):
            return jsonify({"error": "invalid value"}), HTTPStatus.BAD_REQUEST
        if not isfinite(value) or abs(value) > MAX_LOG_ENTRY_VALUE or value < 0:
            return jsonify({"error": "invalid value"}), HTTPStatus.BAD_REQUEST
        entry.value = value

    if "unit" in data:
        unit = data["unit"]
        if not isinstance(unit, str) or len(unit) > 20:
            return jsonify({"error": "invalid unit"}), HTTPStatus.BAD_REQUEST
        entry.unit = unit

    if "notes" in data:
        notes = data["notes"]
        if notes is not None and (
            not isinstance(notes, str) or len(notes) > MAX_LOG_ENTRY_NOTE_CHARS
        ):
            return jsonify({"error": "invalid notes"}), HTTPStatus.BAD_REQUEST
        entry.notes = notes or None

    if "timestamp" in data:
        try:
            new_ts = parse_iso_datetime(str(data["timestamp"]))
        except ValueError:
            return jsonify({"error": "invalid timestamp"}), HTTPStatus.BAD_REQUEST
        if new_ts is None:
            return jsonify({"error": "invalid timestamp"}), HTTPStatus.BAD_REQUEST
        entry.created_at = new_ts

    if entry.entry_type == LogEntryType.BASAL:
        from datetime import timedelta
        from zoneinfo import ZoneInfo

        berlin = ZoneInfo("Europe/Berlin")
        day_start = entry.created_at.astimezone(berlin).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day_end = day_start + timedelta(days=1)
        conflict = (
            LogEntry.query
            .filter_by(user_id=patient.id, entry_type=LogEntryType.BASAL)
            .filter(LogEntry.id != entry.id)
            .filter(LogEntry.created_at >= day_start)
            .filter(LogEntry.created_at < day_end)
            .first()
        )
        if conflict:
            db.session.rollback()
            return jsonify({"error": "basal already logged today"}), HTTPStatus.CONFLICT

    from datetime import UTC, datetime

    entry.updated_at = datetime.now(UTC)
    entry.updated_by_id = user.id
    with transactional_session():
        pass  # commit handled by context manager
    return jsonify(entry.to_dict()), HTTPStatus.OK


@log_bp.route("/", methods=["POST"])
def create_log() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    patient = _get_patient(user)
    if not patient:
        return jsonify({"error": "no patient found"}), HTTPStatus.NOT_FOUND

    data = request.get_json(silent=True) or {}
    try:
        entry_type = LogEntryType(data.get("entry_type", ""))
    except ValueError:
        return jsonify({"error": "invalid entry_type"}), HTTPStatus.BAD_REQUEST

    try:
        value = float(data.get("value", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid value"}), HTTPStatus.BAD_REQUEST
    if not isfinite(value) or abs(value) > MAX_LOG_ENTRY_VALUE:
        return jsonify({"error": "invalid value"}), HTTPStatus.BAD_REQUEST

    notes = data.get("notes")
    if notes is not None and (
        not isinstance(notes, str) or len(notes) > MAX_LOG_ENTRY_NOTE_CHARS
    ):
        return jsonify({"error": "invalid notes"}), HTTPStatus.BAD_REQUEST

    from datetime import UTC, datetime, timedelta
    from zoneinfo import ZoneInfo

    ts_str = data.get("timestamp")
    entry_ts = datetime.now(UTC)
    if ts_str:
        with contextlib.suppress(ValueError):
            entry_ts = parse_iso_datetime(ts_str)

    # Basal: only one per day (Europe/Berlin)
    if entry_type == LogEntryType.BASAL and entry_ts is not None:
        berlin = ZoneInfo("Europe/Berlin")
        day_start = entry_ts.astimezone(berlin).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        existing = (
            LogEntry.query
            .filter_by(user_id=patient.id, entry_type=LogEntryType.BASAL)
            .filter(LogEntry.created_at >= day_start)
            .filter(LogEntry.created_at < day_end)
            .first()
        )
        if existing:
            return jsonify({"error": "basal already logged today"}), HTTPStatus.CONFLICT

    entry = LogEntry(
        user_id=patient.id,
        entry_type=entry_type,
        value=value,
        unit=data.get("unit", "g" if entry_type == LogEntryType.CARBS else "U"),
        notes=notes,
        created_by_id=user.id,
        created_at=entry_ts,
    )
    db.session.add(entry)
    with transactional_session():
        pass  # commit handled by context manager
    return jsonify(entry.to_dict()), HTTPStatus.CREATED


@log_bp.route("/basal-rate", methods=["GET"])
def get_basal_rate() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]
    patient = _get_patient(user)
    if not patient:
        return jsonify({"error": "no patient found"}), HTTPStatus.NOT_FOUND

    current = (
        BasalRateHistory.query.filter_by(user_id=patient.id)
        .order_by(BasalRateHistory.changed_at.desc())
        .first()
    )
    history = (
        BasalRateHistory.query.filter_by(user_id=patient.id)
        .order_by(BasalRateHistory.changed_at.desc())
        .limit(50)
        .all()
    )
    return jsonify({
        "current": {
            "rate": current.rate if current else None,
            "unit": current.unit if current else "U/h",
            "changed_at": current.changed_at.isoformat() if current else None,
        },
        "history": [
            {
                "rate": h.rate,
                "unit": h.unit,
                "changed_at": h.changed_at.isoformat(),
            }
            for h in history
        ],
    })


@log_bp.route("/basal-rate", methods=["POST"])
def update_basal_rate() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]
    if user.role == UserRole.PATIENT:
        return jsonify({"error": "forbidden"}), HTTPStatus.FORBIDDEN

    patient = _get_patient(user)
    if not patient:
        return jsonify({"error": "no patient found"}), HTTPStatus.NOT_FOUND

    data = request.get_json(silent=True) or {}
    new_rate = float(data.get("rate", 0))
    unit = data.get("unit", "U/h")

    prev = (
        BasalRateHistory.query.filter_by(user_id=patient.id)
        .order_by(BasalRateHistory.changed_at.desc())
        .first()
    )
    prev_rate = prev.rate if prev else None

    entry = BasalRateHistory(
        user_id=patient.id,
        rate=new_rate,
        unit=unit,
        changed_by_id=user.id,
    )
    db.session.add(entry)

    if prev_rate is None or prev_rate != new_rate:
        if prev_rate is not None:
            note = (
                f"Basalrate von {prev_rate} auf {new_rate} {unit} geändert. "
                f"({user.display_name})"
            )
        else:
            note = f"Basalrate auf {new_rate} {unit} gesetzt. ({user.display_name})"
        log_entry = LogEntry(
            user_id=patient.id,
            entry_type=LogEntryType.NOTE,
            value=0,
            unit="",
            notes=note,
            created_by_id=user.id,
        )
        db.session.add(log_entry)

    with transactional_session():
        pass  # commit handled by context manager
    return jsonify({"rate": entry.rate, "unit": entry.unit}), HTTPStatus.CREATED


@log_bp.route("/carb-factor", methods=["GET"])
def get_carb_factor() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]
    patient = _get_patient(user)
    if not patient:
        return jsonify({"error": "no patient found"}), HTTPStatus.NOT_FOUND

    current = (
        CarbFactorHistory.query.filter_by(user_id=patient.id)
        .order_by(CarbFactorHistory.changed_at.desc())
        .first()
    )
    history = (
        CarbFactorHistory.query.filter_by(user_id=patient.id)
        .order_by(CarbFactorHistory.changed_at.desc())
        .limit(50)
        .all()
    )
    return jsonify({
        "current": {
            "factor": current.factor if current else None,
            "unit": current.unit if current else "g/IE",
            "changed_at": current.changed_at.isoformat() if current else None,
        },
        "history": [
            {
                "factor": h.factor,
                "unit": h.unit,
                "changed_at": h.changed_at.isoformat(),
            }
            for h in history
        ],
    })


@log_bp.route("/carb-factor", methods=["POST"])
def update_carb_factor() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    patient = _get_patient(user)
    if not patient:
        return jsonify({"error": "no patient found"}), HTTPStatus.NOT_FOUND

    data = request.get_json(silent=True) or {}
    new_factor = float(data.get("factor", 0))
    unit = data.get("unit", "g/IE")

    prev = (
        CarbFactorHistory.query.filter_by(user_id=patient.id)
        .order_by(CarbFactorHistory.changed_at.desc())
        .first()
    )
    prev_factor = prev.factor if prev else None

    entry = CarbFactorHistory(
        user_id=patient.id,
        factor=new_factor,
        unit=unit,
        changed_by_id=user.id,
    )
    db.session.add(entry)

    if prev_factor is None or prev_factor != new_factor:
        if prev_factor is not None:
            note = (
                f"KE-Faktor von {prev_factor} auf {new_factor} {unit} geändert. "
                f"({user.display_name})"
            )
        else:
            note = f"KE-Faktor auf {new_factor} {unit} gesetzt. ({user.display_name})"
        log_entry = LogEntry(
            user_id=patient.id,
            entry_type=LogEntryType.NOTE,
            value=0,
            unit="",
            notes=note,
            created_by_id=user.id,
        )
        db.session.add(log_entry)

    with transactional_session():
        pass  # commit handled by context manager
    return jsonify({"factor": entry.factor, "unit": entry.unit}), HTTPStatus.CREATED


def _get_patient(current_user: User) -> User | None:
    """Return the single patient user."""
    if current_user.role == UserRole.PATIENT:
        return current_user
    return User.query.filter_by(role=UserRole.PATIENT).first()
