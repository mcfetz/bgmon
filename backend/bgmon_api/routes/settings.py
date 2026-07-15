"""Global and user settings management."""

import logging
import threading
from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask import Response as FlaskResponse

from bgmon_api.auth_utils import get_current_user
from bgmon_api.config import Config
from bgmon_api.extensions import db
from bgmon_api.models import GlobalSettings, Threshold, User, UserRole
from bgmon_api.utils import transactional_session

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")
logger = logging.getLogger(__name__)

# ── async ML job tracking ────────────────────────────────────────────────

def _ml_jobs_path() -> str:
    from bgmon_api.config import Config
    return f"{Config.model_dir()}/ml-jobs.json"


def _load_jobs() -> dict[str, dict]:
    try:
        import json as _j
        with open(_ml_jobs_path()) as _f:
            return _j.load(_f)
    except (FileNotFoundError, ValueError):
        return {}


def _save_jobs(jobs: dict[str, dict]) -> None:
    import json as _j
    with open(_ml_jobs_path(), "w") as _f:
        _j.dump(jobs, _f)


def _get_job(job_id: str) -> dict | None:
    return _load_jobs().get(job_id)


def _put_job(job_id: str, data: dict) -> None:
    jobs = _load_jobs()
    jobs[job_id] = data
    _save_jobs(jobs)


@settings_bp.route("/preferences", methods=["GET"])
def get_preferences() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]
    return jsonify({
        "snooze_default_minutes": user.snooze_default_minutes,
        "color_mode": user.color_mode,
        "color_bg": user.color_bg,
        "color_primary": user.color_primary,
    })


@settings_bp.route("/preferences", methods=["PUT"])
def update_preferences() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]
    data = request.get_json(silent=True) or {}
    if "snooze_default_minutes" in data:
        user.snooze_default_minutes = int(data["snooze_default_minutes"])
    if "color_mode" in data:
        mode = data["color_mode"]
        if mode in ("auto", "light", "dark"):
            user.color_mode = mode
    if "color_bg" in data:
        user.color_bg = data["color_bg"] or None
    if "color_primary" in data:
        user.color_primary = data["color_primary"] or None
    with transactional_session():
        pass
    return jsonify({
        "snooze_default_minutes": user.snooze_default_minutes,
        "color_mode": user.color_mode,
        "color_bg": user.color_bg,
        "color_primary": user.color_primary,
    })
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
def get_global_settings() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    settings = GlobalSettings.query.first()
    if not settings:
        settings = GlobalSettings(insulin_action_hours=4.0)
        with transactional_session():
            db.session.add(settings)

    return jsonify(settings.to_dict())


@settings_bp.route("/global", methods=["POST"])
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

    with transactional_session():
        pass  # commit handled by context manager
    return jsonify(settings.to_dict())


@settings_bp.route("/thresholds", methods=["GET"])
def get_thresholds() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    threshold = Threshold.query.filter_by(user_id=user.id).first()
    if not threshold:
        threshold = Threshold(
            user_id=user.id,
            critical_low=54.0,
            low=70.0,
            high=180.0,
            critical_high=250.0,
        )
        with transactional_session():
            db.session.add(threshold)

    return jsonify(threshold.to_dict())


@settings_bp.route("/thresholds", methods=["POST"])
def update_thresholds() -> FlaskResponse | tuple[FlaskResponse, int]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    data = request.get_json(silent=True) or {}

    threshold = Threshold.query.filter_by(user_id=user.id).first()
    if not threshold:
        threshold = Threshold(user_id=user.id)
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

    with transactional_session():
        pass  # commit handled by context manager
    return jsonify(threshold.to_dict())


@settings_bp.route("/password", methods=["POST"])
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
    with transactional_session():
        pass  # commit handled by context manager
    return jsonify({"message": "password changed"})


@settings_bp.route("/email", methods=["POST"])
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
    with transactional_session():
        pass  # commit handled by context manager
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
    with transactional_session():
        pass  # commit handled by context manager
    return jsonify({
        "from_number": user.twilio_from_number,
        "phone_number": user.phone_number,
    })


@settings_bp.route("/twilio/test", methods=["POST"])
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
        db.session.add(LogEntry(
            user_id=user.id,
            entry_type=LogEntryType.ALARM,
            value=0,
            unit="",
            notes=note,
        ))
        with transactional_session():
            pass  # commit handled by context manager

        return jsonify({
            "message": "Test call initiated",
            "sid": call.sid,
            "to": user.phone_number,
            "from": from_number,
        })
    except Exception as exc:
        from bgmon_api.models import LogEntry, LogEntryType
        note = f"Testanruf an {user.display_name} ({user.email}) via Twilio FEHLGESCHLAGEN: {exc}"
        db.session.add(LogEntry(
            user_id=user.id,
            entry_type=LogEntryType.ALARM,
            value=0,
            unit="",
            notes=note,
        ))
        with transactional_session():
            pass  # commit handled by context manager
        return jsonify({"error": f"Twilio call failed: {exc}"}), HTTPStatus.SERVICE_UNAVAILABLE


# ── ML endpoints ─────────────────────────────────────────────────────────


def _run_train(job_id: str) -> None:
    from pathlib import Path  # noqa: PLC0415

    from bgmon_api.app import _app  # noqa: PLC0415
    from bgmon_api.commands.train_predictor import _collect_training_data  # noqa: PLC0415
    from bgmon_api.services.model_publisher import publish_model  # noqa: PLC0415
    from bgmon_api.services.model_trainer import (  # noqa: PLC0415
        ModelTrainer,
        TrainingInsufficientError,
    )

    if _app is None:
        _put_job(job_id, {"status": "failed", "error": "App not initialized"})
        return

    try:
        with _app.app_context():
            target_dir = Path(Config.model_dir())
            training_input = _collect_training_data()
            trainer = ModelTrainer(cv_splits=min(5, max(2, training_input.sample_count - 1)))
            result = trainer.train(training_input)
            publish_model(result, target_dir)
            db.session.remove()

            _put_job(job_id, {
                    "status": "completed",
                    "samples": training_input.sample_count,
                    "metrics": [
                        {"horizon": m.horizon_minutes, "baseline_mae": round(m.baseline_mae, 1),
                         "model_mae": round(m.model_mae, 1), "n_splits": m.n_splits}
                        for m in result.metrics
                    ],
                })
    except TrainingInsufficientError:
        _put_job(job_id, {
            "status": "failed",
            "error": "Nicht genügend Trainingsdaten (mind. 3 Samples nötig).",
        })
    except Exception:
        logger.exception("ML training job %s failed", job_id)
        _put_job(job_id, {"status": "failed", "error": "Training fehlgeschlagen."})


@settings_bp.route("/ml/train", methods=["POST"])
def ml_train_start() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]
    if user.role != UserRole.ADMIN:
        return jsonify({"error": "forbidden"}), HTTPStatus.FORBIDDEN

    import uuid  # noqa: PLC0415

    job_id = uuid.uuid4().hex[:12]
    _put_job(job_id, {"status": "running"})

    thread = threading.Thread(target=_run_train, args=(job_id,))
    thread.start()

    return jsonify({"job_id": job_id, "status": "running"})


@settings_bp.route("/ml/train/<job_id>", methods=["GET"])
def ml_train_status(job_id: str) -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    job = _get_job(job_id)
    if not job:
        return jsonify({"error": "not_found"}), HTTPStatus.NOT_FOUND
    return jsonify(job)


def _run_evaluate(job_id: str) -> None:
    """Execute flask predictor evaluate in a background thread."""
    from bgmon_api.app import _app  # noqa: PLC0415
    from bgmon_api.services.prediction_evaluator import (  # noqa: PLC0415
        evaluate_saved_predictions,
    )

    if _app is None:
        _put_job(job_id, {"status": "failed", "error": "App not initialized"})
        return

    try:
        with _app.app_context():
            report = evaluate_saved_predictions()
            db.session.remove()
            summaries = [
                {
                    "horizon": s.horizon_minutes,
                    "model_version": s.model_version,
                    "mae": round(s.mae, 1) if s.mae is not None else None,
                    "matched_points": s.matched_points,
                    "completed_runs": s.completed_runs,
                    "run_count": s.run_count,
                }
                for s in report.aggregate_summaries
            ]
            _put_job(job_id, {"status": "completed", "summaries": summaries})
    except Exception:
        logger.exception("ML evaluation job %s failed", job_id)
        _put_job(job_id, {"status": "failed", "error": "Evaluierung fehlgeschlagen."})


@settings_bp.route("/ml/evaluate", methods=["POST"])
def ml_evaluate_start() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]
    if user.role != UserRole.ADMIN:
        return jsonify({"error": "forbidden"}), HTTPStatus.FORBIDDEN

    import uuid  # noqa: PLC0415

    job_id = uuid.uuid4().hex[:12]
    _put_job(job_id, {"status": "running"})

    thread = threading.Thread(target=_run_evaluate, args=(job_id,))
    thread.start()

    return jsonify({"job_id": job_id, "status": "running"})


@settings_bp.route("/ml/evaluate/<job_id>", methods=["GET"])
def ml_evaluate_status(job_id: str) -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    job = _get_job(job_id)
    if not job:
        return jsonify({"error": "not_found"}), HTTPStatus.NOT_FOUND
    return jsonify(job)
