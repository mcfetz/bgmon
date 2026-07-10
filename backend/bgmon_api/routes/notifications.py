"""Notification profiles API."""

from datetime import UTC, datetime, timedelta
from datetime import time as time_cls
from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask import Response as FlaskResponse

from bgmon_api.auth_utils import get_current_user
from bgmon_api.extensions import db
from bgmon_api.models import (
    NotificationArea,
    NotificationAssignment,
    NotificationProfile,
    NotificationThreshold,
    UserActiveProfile,
    UserSnooze,
)
from bgmon_api.utils import transactional_session

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


_VALID_AREAS = {a.value for a in NotificationArea}
_VALID_THRESHOLDS = {t.value for t in NotificationThreshold}


def _parse_assignments(raw):
    """Validate and normalize assignments list.

    Returns (assignments_dict, error_response). On error, assignments_dict is None.
    """
    if not isinstance(raw, list):
        return None, (jsonify({"error": "assignments must be a list"}), HTTPStatus.BAD_REQUEST)
    seen_thresholds: set[str] = set()
    normalized: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            return None, (
                jsonify({"error": "each assignment must be an object"}),
                HTTPStatus.BAD_REQUEST,
            )
        area = item.get("area", "").strip()
        threshold = item.get("threshold", "").strip()
        if area not in _VALID_AREAS:
            return None, (jsonify({"error": f"invalid area: {area}"}), HTTPStatus.BAD_REQUEST)
        if threshold not in _VALID_THRESHOLDS:
            return None, (
                jsonify({"error": f"invalid threshold: {threshold}"}),
                HTTPStatus.BAD_REQUEST,
            )
        if threshold in seen_thresholds:
            return None, (
                jsonify({"error": f"threshold {threshold} assigned multiple times"}),
                HTTPStatus.BAD_REQUEST,
            )
        seen_thresholds.add(threshold)
        normalized[threshold] = area
    return normalized, None


@notifications_bp.route("/profiles", methods=["GET"])
def list_profiles() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    profiles = (
        NotificationProfile.query.filter_by(user_id=user.id)
        .order_by(NotificationProfile.created_at)
        .all()
    )
    return jsonify([p.to_dict() for p in profiles])


@notifications_bp.route("/profiles", methods=["POST"])
def create_profile() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "name required"}), HTTPStatus.BAD_REQUEST
    if len(name) > 100:
        return jsonify({"error": "name too long (max 100)"}), HTTPStatus.BAD_REQUEST
    icon = str(data.get("icon", "🔔"))[:10]

    normalized, err = _parse_assignments(data.get("assignments", []))
    if err:
        return err

    profile = NotificationProfile(user_id=user.id, name=name, icon=icon)
    db.session.add(profile)
    db.session.flush()

    for threshold, area in normalized.items():
        db.session.add(
            NotificationAssignment(
                profile_id=profile.id,
                area=NotificationArea(area),
                threshold=NotificationThreshold(threshold),
            )
        )

    with transactional_session():
        pass  # commit handled by context manager
    return jsonify(profile.to_dict()), HTTPStatus.CREATED


@notifications_bp.route("/profiles/<int:profile_id>", methods=["PATCH"])
def update_profile(profile_id: int) -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    profile = NotificationProfile.query.filter_by(id=profile_id, user_id=user.id).first()
    if not profile:
        return jsonify({"error": "not found"}), HTTPStatus.NOT_FOUND

    data = request.get_json(silent=True) or {}

    if "name" in data:
        name = str(data.get("name", "")).strip()
        if not name:
            return jsonify({"error": "name required"}), HTTPStatus.BAD_REQUEST
        if len(name) > 100:
            return jsonify({"error": "name too long (max 100)"}), HTTPStatus.BAD_REQUEST
        profile.name = name

    if "icon" in data:
        profile.icon = str(data.get("icon", "🔔"))[:10]

    if "start_time" in data:
        raw = data.get("start_time")
        if raw in (None, "", "null"):
            profile.start_time = None
        else:
            try:
                hh, mm = str(raw).split(":")
                profile.start_time = time_cls(int(hh), int(mm))
            except (ValueError, AttributeError):
                return jsonify({"error": "start_time must be HH:MM"}), HTTPStatus.BAD_REQUEST

    if "assignments" in data:
        normalized, err = _parse_assignments(data.get("assignments"))
        if err:
            return err
        NotificationAssignment.query.filter_by(profile_id=profile.id).delete()
        for threshold, area in normalized.items():
            db.session.add(
                NotificationAssignment(
                    profile_id=profile.id,
                    area=NotificationArea(area),
                    threshold=NotificationThreshold(threshold),
                )
            )

    with transactional_session():
        pass  # commit handled by context manager
    return jsonify(profile.to_dict())


@notifications_bp.route("/profiles/<int:profile_id>", methods=["DELETE"])
def delete_profile(profile_id: int) -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    profile = NotificationProfile.query.filter_by(id=profile_id, user_id=user.id).first()
    if not profile:
        return jsonify({"error": "not found"}), HTTPStatus.NOT_FOUND

    db.session.delete(profile)
    with transactional_session():
        pass  # commit handled by context manager
    return jsonify({"deleted": profile_id})


@notifications_bp.route("/active", methods=["GET"])
def get_active_profile() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    active = UserActiveProfile.query.get(user.id)
    if not active:
        return jsonify({"profile_id": None, "profile": None})

    profile = NotificationProfile.query.get(active.profile_id)
    return jsonify({
        "profile_id": active.profile_id,
        "profile": profile.to_dict() if profile else None,
    })


@notifications_bp.route("/active", methods=["PUT"])
def set_active_profile() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    data = request.get_json(silent=True) or {}
    profile_id = data.get("profile_id")

    if profile_id is not None:
        profile = NotificationProfile.query.filter_by(id=profile_id, user_id=user.id).first()
        if not profile:
            return jsonify({"error": "profile not found"}), HTTPStatus.NOT_FOUND

    active = UserActiveProfile.query.get(user.id)
    if not active:
        active = UserActiveProfile(user_id=user.id, profile_id=profile_id)
        db.session.add(active)
    else:
        active.profile_id = profile_id
    with transactional_session():
        pass  # commit handled by context manager
    return jsonify(active.to_dict())


@notifications_bp.route("/active/<int:profile_id>", methods=["GET"])
def webhook_activate_profile(profile_id: int) -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    profile = NotificationProfile.query.get(profile_id)
    if not profile:
        return jsonify({"error": "profile not found"}), HTTPStatus.NOT_FOUND

    owner_id = profile.user_id
    active = UserActiveProfile.query.get(owner_id)
    if not active:
        active = UserActiveProfile(user_id=owner_id, profile_id=profile_id)
        db.session.add(active)
    else:
        active.profile_id = profile_id
    with transactional_session():
        pass  # commit handled by context manager

    return jsonify({
        "message": f"Active profile set to '{profile.name}' (id={profile_id}) for user {owner_id}."
    })


@notifications_bp.route("/snooze", methods=["GET"])
def get_snooze() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    snooze = UserSnooze.query.get(user.id)
    if not snooze or not snooze.is_active:
        return jsonify({"snooze_until": None, "reason": None, "active": False})
    return jsonify({**snooze.to_dict(), "active": True})


@notifications_bp.route("/snooze", methods=["POST"])
def set_snooze() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    data = request.get_json(silent=True) or {}
    minutes = int(data.get("minutes", 15))
    reason = data.get("reason")

    snooze = UserSnooze.query.get(user.id) or UserSnooze(user_id=user.id)
    snooze.snooze_until = datetime.now(UTC) + timedelta(minutes=minutes)
    snooze.reason = reason
    if snooze not in db.session:
        db.session.add(snooze)
    with transactional_session():
        pass  # commit handled by context manager
    return jsonify({**snooze.to_dict(), "active": True})


@notifications_bp.route("/snooze", methods=["DELETE"])
def clear_snooze() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    snooze = UserSnooze.query.get(user.id)
    if snooze:
        db.session.delete(snooze)
        with transactional_session():
            pass  # commit handled by context manager
    return jsonify({"cleared": True})


@notifications_bp.route("/snooze", methods=["PATCH"])
def adjust_snooze() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    data = request.get_json(silent=True) or {}
    delta = int(data.get("delta_minutes", 0))

    snooze = UserSnooze.query.get(user.id)
    if not snooze:
        snooze = UserSnooze(user_id=user.id, snooze_until=datetime.now(UTC))
        db.session.add(snooze)

    new_until = snooze.snooze_until + timedelta(minutes=delta)
    if new_until < datetime.now(UTC):
        new_until = datetime.now(UTC) + timedelta(minutes=1)

    snooze.snooze_until = new_until
    with transactional_session():
        pass  # commit handled by context manager
    return jsonify({**snooze.to_dict(), "active": True})
