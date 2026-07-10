"""Shift management blueprint — only one active observer shift at a time."""

from http import HTTPStatus

from flask import Blueprint, jsonify
from flask import Response as FlaskResponse

from bgmon_api.auth_utils import get_current_user
from bgmon_api.extensions import db
from bgmon_api.models import Shift, UserRole
from bgmon_api.utils import transactional_session

shifts_bp = Blueprint("shifts", __name__)


def _get_active_shift() -> Shift | None:
    return Shift.query.filter_by(active=True).first()


@shifts_bp.route("/active", methods=["GET"])
def get_active_shift() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    shift = _get_active_shift()
    if not shift:
        return jsonify({"active": False, "shift": None})

    return jsonify({
        "active": True,
        "shift": {
            "id": shift.id,
            "user_id": shift.user_id,
            "user_name": shift.user.display_name if shift.user else None,
            "started_at": shift.started_at.isoformat(),
        },
    })


@shifts_bp.route("/start", methods=["POST"])
def start_shift() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]
    if user.role == UserRole.PATIENT:
        return jsonify({"error": "patient cannot take shift"}), HTTPStatus.FORBIDDEN

    # End any existing active shift
    existing = _get_active_shift()
    if existing:
        from datetime import UTC, datetime

        existing.active = False
        existing.ended_at = datetime.now(UTC)
        with transactional_session():
            pass  # commit handled by context manager

    shift = Shift(user_id=user.id, active=True)
    db.session.add(shift)
    with transactional_session():
        pass  # commit handled by context manager

    return jsonify({
        "status": "started",
        "shift_id": shift.id,
        "started_at": shift.started_at.isoformat(),
    })


@shifts_bp.route("/end", methods=["POST"])
def end_shift() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    active = _get_active_shift()
    if not active:
        return jsonify({"error": "no active shift"}), HTTPStatus.BAD_REQUEST

    if active.user_id != user.id and user.role != UserRole.ADMIN:
        return jsonify({"error": "not your shift"}), HTTPStatus.FORBIDDEN

    from datetime import UTC, datetime

    active.active = False
    active.ended_at = datetime.now(UTC)
    with transactional_session():
        pass  # commit handled by context manager

    return jsonify({"status": "ended"})


@shifts_bp.route("/history", methods=["GET"])
def shift_history() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    shifts = (
        Shift.query.filter_by(user_id=user.id)
        .order_by(Shift.started_at.desc())
        .limit(50)
        .all()
    )

    return jsonify({
        "shifts": [
            {
                "id": s.id,
                "active": s.active,
                "started_at": s.started_at.isoformat(),
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            }
            for s in shifts
        ],
    })
