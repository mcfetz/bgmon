"""Authentication blueprint — login, logout, session."""

import logging
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask import Response as FlaskResponse
from sqlalchemy.exc import SQLAlchemyError

from bgmon_api.auth_utils import get_current_user
from bgmon_api.extensions import db, limiter
from bgmon_api.models import Session, User
from bgmon_api.utils import transactional_session

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("10 per minute;30 per hour")
def login() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    data = request.get_json(silent=True) or {}
    email = data.get("email", "")
    password = data.get("password", "")

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "invalid credentials"}), HTTPStatus.UNAUTHORIZED

    if not user.is_active:
        return jsonify({"error": "account deactivated"}), HTTPStatus.UNAUTHORIZED

    user_data = {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role.value,
        "is_active": user.is_active,
    }

    try:
        with transactional_session():
            session = Session()
            session.user_id = user.id
            session.expires_at = datetime.now(UTC) + timedelta(days=30)
            db.session.add(session)
            db.session.flush()
            token = session.token

        return jsonify({"token": token, "user": user_data})
    except SQLAlchemyError:
        logger.exception("Failed to create session for user_id=%s", user.id)
        return jsonify({"error": "Failed to create session"}), HTTPStatus.INTERNAL_SERVER_ERROR


@auth_bp.route("/me", methods=["GET"])
def me() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]
    return jsonify(user.to_dict())


@auth_bp.route("/logout", methods=["POST"])
def logout() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.removeprefix("Bearer ")
        session = Session.query.filter_by(token=token).first()
        if session:
            try:
                with transactional_session():
                    db.session.delete(session)
            except SQLAlchemyError:
                logger.exception("Failed to revoke session for user_id=%s", session.user_id)
                return (
                    jsonify({"error": "Failed to revoke session"}),
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
    return jsonify({"status": "ok"})
