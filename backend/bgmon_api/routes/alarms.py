"""Alarm and push subscription blueprint."""

from datetime import UTC
from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask import Response as FlaskResponse

from bgmon_api.app import db
from bgmon_api.auth_utils import get_current_user
from bgmon_api.models import Alarm, PushSubscription, User, UserRole

alarms_bp = Blueprint("alarms", __name__)


@alarms_bp.route("/active", methods=["GET"])
def get_active_alarms() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    patient = User.query.filter_by(role=UserRole.PATIENT).first()
    if not patient:
        return jsonify({"alarms": []}), HTTPStatus.OK

    alarms = Alarm.query.filter_by(
        user_id=patient.id,
        acknowledged_at=None,
    ).order_by(Alarm.created_at.desc()).all()

    return jsonify({
        "alarms": [
            {
                "id": a.id,
                "type": a.alarm_type.value,
                "sgv": a.sgv,
                "escalation_count": a.escalation_count,
                "created_at": a.created_at.isoformat(),
            }
            for a in alarms
        ],
    })


@alarms_bp.route("/<int:alarm_id>/acknowledge", methods=["POST"])
def acknowledge_alarm(alarm_id: int) -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    alarm = Alarm.query.get(alarm_id)
    if not alarm:
        return jsonify({"error": "not found"}), HTTPStatus.NOT_FOUND

    from datetime import datetime

    alarm.acknowledged_at = datetime.now(UTC)
    db.session.commit()
    return jsonify({"status": "acknowledged"})


@alarms_bp.route("/subscribe", methods=["POST"])
def subscribe_push() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    p256dh = data.get("p256dh")
    auth = data.get("auth")

    if not endpoint or not p256dh or not auth:
        return jsonify({"error": "missing subscription fields"}), HTTPStatus.BAD_REQUEST

    # Remove existing subscription for same endpoint to avoid duplicates
    existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existing:
        db.session.delete(existing)

    sub = PushSubscription(
        user_id=user.id,
        endpoint=endpoint,
        p256dh_key=p256dh,
        auth_key=auth,
    )
    db.session.add(sub)
    db.session.commit()
    return jsonify({"status": "subscribed"}), HTTPStatus.CREATED


@alarms_bp.route("/unsubscribe", methods=["POST"])
def unsubscribe_push() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")

    if endpoint:
        sub = PushSubscription.query.filter_by(endpoint=endpoint).first()
    else:
        sub = PushSubscription.query.filter_by(user_id=user.id).first()

    if sub:
        db.session.delete(sub)
        db.session.commit()
        return jsonify({"status": "unsubscribed"})

    return jsonify({"error": "not found"}), HTTPStatus.NOT_FOUND


@alarms_bp.route("/vapid-public-key", methods=["GET"])
def vapid_public_key() -> FlaskResponse:
    from bgmon_api.config import Config

    return jsonify({"public_key": Config.VAPID_PUBLIC_KEY})


@alarms_bp.route("/test-push", methods=["POST"])
def test_push() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    from bgmon_api.services.web_push import send_push_to_user

    send_push_to_user(user.id, "bgmon Test", "Push-Benachrichtigungen funktionieren.")
    return jsonify({"message": "test push sent"})
