"""Global and user settings management."""

from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask import Response as FlaskResponse

from bgmon_api.auth_utils import get_current_user
from bgmon_api.config import Config
from bgmon_api.extensions import db
from bgmon_api.models import GlobalSettings, Threshold, User, UserRole
from bgmon_api.utils import transactional

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")


@settings_bp.route("/libre/reload-history", methods=["POST"])
def reload_libre_history() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]
    if user.role == UserRole.PATIENT:
        return jsonify({"error": "forbidden"}), HTTPStatus.FORBIDDEN

    from bgmon_api.services.libre_fetcher import fetch_and_store

    try:
        fetch_and_store(fetch_history=True)
        return jsonify({"message": "Historische Daten erfolgreich geladen"})
    except Exception as e:
        return jsonify({"error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR


@settings_bp.route("/global", methods=["GET"])
@transactional
def get_global_settings() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    settings = GlobalSettings.query.first()
    if not settings:
        settings = GlobalSettings()
        settings.insulin_action_hours = 4.0
        db.session.add(settings)

    return jsonify(settings.to_dict())


@settings_bp.route("/global", methods=["POST"])
@transactional
def update_global_settings() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]
    if user.role == UserRole.PATIENT:
        return jsonify({"error": "forbidden"}), HTTPStatus.FORBIDDEN

    data = request.get_json(silent=True) or {}
    insulin_hours = data.get("insulin_action_hours")
    correction_factor = data.get("correction_factor")

    if insulin_hours is not None and (
        not isinstance(insulin_hours, (int, float)) or insulin_hours <= 0
    ):
        return (
            jsonify({"error": "insulin_action_hours must be positive number"}),
            HTTPStatus.BAD_REQUEST,
        )

    if correction_factor is not None and (
        not isinstance(correction_factor, (int, float)) or correction_factor <= 0
    ):
        return (
            jsonify({"error": "correction_factor must be positive number"}),
            HTTPStatus.BAD_REQUEST,
        )

    settings = GlobalSettings.query.first()
    if not settings:
        settings = GlobalSettings()
        db.session.add(settings)

    if insulin_hours is not None:
        settings.insulin_action_hours = float(insulin_hours)

    if correction_factor is not None:
        settings.correction_factor = float(correction_factor)

    return jsonify(settings.to_dict())


@settings_bp.route("/thresholds", methods=["GET"])
@transactional
def get_thresholds() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    threshold = Threshold.query.filter_by(user_id=user.id).first()
    if not threshold:
        threshold = Threshold()
        threshold.user_id = user.id
        threshold.critical_low = 54.0
        threshold.low = 70.0
        threshold.high = 180.0
        threshold.critical_high = 250.0
        db.session.add(threshold)

    return jsonify(threshold.to_dict())


@settings_bp.route("/thresholds", methods=["POST"])
@transactional
def update_thresholds() -> FlaskResponse | tuple[FlaskResponse, int]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    data = request.get_json(silent=True) or {}

    threshold = Threshold.query.filter_by(user_id=user.id).first()
    if not threshold:
        threshold = Threshold()
        threshold.user_id = user.id
        db.session.add(threshold)

    for field in ["critical_low", "low", "high", "critical_high"]:
        if field in data:
            val = data[field]
            if not isinstance(val, (int, float)):
                return jsonify({"error": f"{field} must be number"}), HTTPStatus.BAD_REQUEST
            setattr(threshold, field, float(val))

    if threshold.critical_low >= threshold.low:
        return jsonify({"error": "critical_low must be < low"}), HTTPStatus.BAD_REQUEST
    if threshold.low >= threshold.high:
        return jsonify({"error": "low must be < high"}), HTTPStatus.BAD_REQUEST
    if threshold.high >= threshold.critical_high:
        return jsonify({"error": "high must be < critical_high"}), HTTPStatus.BAD_REQUEST

    return jsonify(threshold.to_dict())


@settings_bp.route("/password", methods=["POST"])
@transactional
def change_password() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_password or not new_password:
        return (
            jsonify({"error": "current_password and new_password required"}),
            HTTPStatus.BAD_REQUEST,
        )

    if not user.check_password(current_password):
        return jsonify({"error": "current password incorrect"}), HTTPStatus.UNAUTHORIZED

    if len(new_password) < 6:
        return (
            jsonify({"error": "new password must be at least 6 characters"}),
            HTTPStatus.BAD_REQUEST,
        )

    user.set_password(new_password)
    return jsonify({"message": "password changed"})


@settings_bp.route("/email", methods=["POST"])
@transactional
def update_email() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    data = request.get_json(silent=True) or {}
    new_email = data.get("email", "").strip()

    if not new_email:
        return jsonify({"error": "email required"}), HTTPStatus.BAD_REQUEST

    if "@" not in new_email or "." not in new_email:
        return jsonify({"error": "invalid email format"}), HTTPStatus.BAD_REQUEST

    existing = User.query.filter(User.email == new_email, User.id != user.id).first()
    if existing:
        return jsonify({"error": "email already in use"}), HTTPStatus.CONFLICT

    user.email = new_email
    return jsonify({"email": user.email})


@settings_bp.route("/twilio/numbers", methods=["GET"])
def get_twilio_numbers() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    available = Config.get_twilio_numbers()
    return jsonify({
        "numbers": available,
        "current": user.twilio_from_number or Config.TWILIO_FROM_NUMBER or "",
    })


@settings_bp.route("/twilio", methods=["POST"])
@transactional
def update_twilio() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    data = request.get_json(silent=True) or {}
    from_number = data.get("from_number", "").strip()
    new_phone = data.get("phone_number", "").strip() if "phone_number" in data else None

    if not from_number:
        return jsonify({"error": "from_number required"}), HTTPStatus.BAD_REQUEST

    available = Config.get_twilio_numbers()
    if from_number not in available:
        return jsonify({"error": "number not in configured Twilio numbers"}), HTTPStatus.BAD_REQUEST

    effective_phone = new_phone if new_phone is not None else (user.phone_number or "")
    if from_number == effective_phone:
        return (
            jsonify({"error": "from_number and phone_number must differ"}),
            HTTPStatus.BAD_REQUEST,
        )

    if new_phone is not None:
        user.phone_number = new_phone
    user.twilio_from_number = from_number
    return jsonify({
        "from_number": user.twilio_from_number,
        "phone_number": user.phone_number,
    })


@settings_bp.route("/twilio/test", methods=["POST"])
@transactional
def test_twilio_call() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    if not user.phone_number:
        return jsonify({"error": "no phone_number configured"}), HTTPStatus.BAD_REQUEST

    from bgmon_api.services.twilio_caller import _get_client

    client = _get_client()
    if client is None:
        return jsonify({"error": "Twilio not configured on server"}), HTTPStatus.SERVICE_UNAVAILABLE

    from_number = user.twilio_from_number or Config.TWILIO_FROM_NUMBER
    if not from_number:
        return jsonify({"error": "no from_number configured"}), HTTPStatus.BAD_REQUEST

    if from_number == user.phone_number:
        return (
            jsonify({"error": "from_number and phone_number must differ"}),
            HTTPStatus.BAD_REQUEST,
        )

    try:
        call = client.calls.create(
            to=user.phone_number,
            from_=from_number,
            twiml=(
                '<Response><Say voice="alice" language="de-DE">'
                "Dies ist ein Testanruf von bgmon. Die Twilio Anbindung funktioniert."
                "</Say></Response>"
            ),
        )

        from bgmon_api.models import LogEntry, LogEntryType
        note = (
            f"Testanruf an {user.display_name} ({user.email}) via Twilio: "
            f"from={from_number} to={user.phone_number}, status={call.status}"
        )
        log_entry = LogEntry()
        log_entry.user_id = user.id
        log_entry.entry_type = LogEntryType.ALARM
        log_entry.value = 0
        log_entry.unit = ""
        log_entry.notes = note
        db.session.add(log_entry)

        return jsonify({
            "message": "Test call initiated",
            "sid": call.sid,
            "to": user.phone_number,
            "from": from_number,
        })
    except Exception as exc:
        from bgmon_api.models import LogEntry, LogEntryType
        note = f"Testanruf an {user.display_name} ({user.email}) via Twilio FEHLGESCHLAGEN: {exc}"
        log_entry = LogEntry()
        log_entry.user_id = user.id
        log_entry.entry_type = LogEntryType.ALARM
        log_entry.value = 0
        log_entry.unit = ""
        log_entry.notes = note
        db.session.add(log_entry)
        return jsonify({"error": f"Twilio call failed: {exc}"}), HTTPStatus.SERVICE_UNAVAILABLE
