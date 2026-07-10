"""Night profile and secret webhook blueprint."""

from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask import Response as FlaskResponse

from bgmon_api.auth_utils import get_current_user
from bgmon_api.extensions import db
from bgmon_api.models import NightProfile, Shift, User, UserRole

night_bp = Blueprint("night", __name__)


def _get_patient() -> User | None:
    return User.query.filter_by(role=UserRole.PATIENT).first()


@night_bp.route("/profile", methods=["GET"])
def get_profile() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    patient = _get_patient()
    if not patient:
        return jsonify({"error": "no patient"}), HTTPStatus.NOT_FOUND

    profile = NightProfile.query.filter_by(user_id=patient.id).first()
    if not profile:
        profile = NightProfile(user_id=patient.id)
        db.session.add(profile)
        db.session.commit()

    return jsonify(profile.to_dict())


@night_bp.route("/profile", methods=["POST"])
def update_profile() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    patient = _get_patient()
    if not patient:
        return jsonify({"error": "no patient"}), HTTPStatus.NOT_FOUND

    profile = NightProfile.query.filter_by(user_id=patient.id).first()
    if not profile:
        profile = NightProfile(user_id=patient.id)
        db.session.add(profile)

    data = request.get_json(silent=True) or {}
    if "enabled" in data:
        profile.enabled = bool(data["enabled"])
    if "start_time" in data:
        profile.start_time = data["start_time"]
    if "end_time" in data:
        profile.end_time = data["end_time"]

    db.session.commit()
    return jsonify(profile.to_dict())


@night_bp.route("/webhook/<token>", methods=["POST"])
def webhook_activate(token: str) -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    """Secret webhook to activate night mode for the on-call observer."""
    profile = NightProfile.query.filter_by(webhook_token=token).first()
    if not profile:
        return jsonify({"error": "invalid token"}), HTTPStatus.NOT_FOUND

    # Find the active shift holder to notify
    active_shift = Shift.query.filter_by(active=True).first()
    if not active_shift:
        return jsonify({"error": "no active shift"}), HTTPStatus.BAD_REQUEST

    profile.enabled = True
    db.session.commit()

    from bgmon_api.services.web_push import send_push_to_user

    send_push_to_user(
        active_shift.user_id,
        "Nachtmodus aktiviert",
        "Der Nachtmodus wurde über Webhook aktiviert.",
    )

    return jsonify({"status": "activated"})
