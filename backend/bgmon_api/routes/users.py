"""User management blueprint — CRUD for users, role enforcement."""

import contextlib
from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask import Response as FlaskResponse

from bgmon_api.auth_utils import admin_required, get_current_user
from bgmon_api.extensions import db
from bgmon_api.models import NightProfile, SnoozePreset, Threshold, User, UserRole
from bgmon_api.utils import transactional

users_bp = Blueprint("users", __name__)


def _require_owner_or_admin(current: User, user_id: int) -> tuple[dict, HTTPStatus] | None:
    """Check that the current user owns the target resource or is an admin."""
    if current.id == user_id:
        return None
    return admin_required(current)


@users_bp.route("", methods=["GET"])
def list_users() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    current = get_current_user()
    if isinstance(current, tuple):
        return jsonify(current[0]), current[1]
    err = admin_required(current)
    if err:
        return jsonify(err[0]), err[1]
    users = User.query.order_by(User.display_name).all()
    return jsonify([u.to_dict() for u in users])


@users_bp.route("/<int:user_id>", methods=["GET"])
def get_user(user_id: int) -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    current = get_current_user()
    if isinstance(current, tuple):
        return jsonify(current[0]), current[1]
    err = _require_owner_or_admin(current, user_id)
    if err:
        return jsonify(err[0]), err[1]
    target = db.session.get(User, user_id)
    if not target:
        return jsonify({"error": "not found"}), HTTPStatus.NOT_FOUND
    return jsonify(target.to_dict())


@users_bp.route("", methods=["POST"])
@transactional
def create_user() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    current = get_current_user()
    if isinstance(current, tuple):
        return jsonify(current[0]), current[1]
    err = admin_required(current)
    if err:
        return jsonify(err[0]), err[1]

    data = request.get_json(silent=True) or {}
    email = data.get("email", "")
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email exists"}), HTTPStatus.CONFLICT

    try:
        role = UserRole(data.get("role", UserRole.OBSERVER.value))
    except ValueError:
        role = UserRole.OBSERVER

    new_user = User()
    new_user.email = email
    new_user.display_name = data.get("display_name", email.split("@")[0])
    new_user.role = role
    new_user.set_password(data.get("password", "changeme"))
    db.session.add(new_user)
    db.session.flush()

    threshold = Threshold()
    threshold.user_id = new_user.id
    db.session.add(threshold)

    night_profile = NightProfile()
    night_profile.user_id = new_user.id
    db.session.add(night_profile)
    for label, mins in [
        ("5 min", 5),
        ("10 min", 10),
        ("15 min", 15),
        ("20 min", 20),
        ("30 min", 30),
        ("60 min", 60),
    ]:
        preset = SnoozePreset()
        preset.user_id = new_user.id
        preset.label = label
        preset.duration_minutes = mins
        db.session.add(preset)

    return jsonify(new_user.to_dict()), HTTPStatus.CREATED


@users_bp.route("/<int:user_id>", methods=["PUT"])
@transactional
def update_user(user_id: int) -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    current = get_current_user()
    if isinstance(current, tuple):
        return jsonify(current[0]), current[1]
    if current.id != user_id:
        err = admin_required(current)
        if err:
            return jsonify(err[0]), err[1]

    target = db.session.get(User, user_id)
    if not target:
        return jsonify({"error": "not found"}), HTTPStatus.NOT_FOUND

    data = request.get_json(silent=True) or {}
    if "display_name" in data:
        target.display_name = data["display_name"]
    if "is_active" in data:
        target.is_active = bool(data["is_active"])
    if "password" in data and data["password"]:
        target.set_password(data["password"])
    if "role" in data and current.role == UserRole.ADMIN:
        with contextlib.suppress(ValueError):
            target.role = UserRole(data["role"])

    return jsonify(target.to_dict())


@users_bp.route("/<int:user_id>/thresholds", methods=["GET", "PUT"])
@transactional
def thresholds(user_id: int) -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    current = get_current_user()
    if isinstance(current, tuple):
        return jsonify(current[0]), current[1]
    err = _require_owner_or_admin(current, user_id)
    if err:
        return jsonify(err[0]), err[1]
    target = db.session.get(User, user_id)
    if not target:
        return jsonify({"error": "not found"}), HTTPStatus.NOT_FOUND

    th = Threshold.query.filter_by(user_id=user_id).first()
    if not th:
        th = Threshold()
        th.user_id = user_id
        db.session.add(th)

    if request.method == "PUT":
        data = request.get_json(silent=True) or {}
        if "critical_low" in data:
            th.critical_low = float(data["critical_low"])
        if "low" in data:
            th.low = float(data["low"])
        if "high" in data:
            th.high = float(data["high"])
        if "critical_high" in data:
            th.critical_high = float(data["critical_high"])

    return jsonify(th.to_dict())


@users_bp.route("/<int:user_id>/snooze-presets", methods=["GET"])
def snooze_presets(user_id: int) -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    current = get_current_user()
    if isinstance(current, tuple):
        return jsonify(current[0]), current[1]
    err = _require_owner_or_admin(current, user_id)
    if err:
        return jsonify(err[0]), err[1]
    presets = (
        SnoozePreset.query.filter_by(user_id=user_id).order_by(SnoozePreset.duration_minutes).all()
    )
    return jsonify([p.to_dict() for p in presets])
