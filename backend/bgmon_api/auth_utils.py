"""Shared auth helpers for blueprints."""

from datetime import UTC, datetime
from http import HTTPStatus
from typing import cast

from flask import request


def get_current_user():
    """Return authenticated user or (error_dict, status) tuple."""
    from bgmon_api.models import Session, User

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return ({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
    token = auth.removeprefix("Bearer ")
    session = Session.query.filter(
        Session.token == token, Session.expires_at > datetime.now(UTC)
    ).first()
    if not session:
        return ({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
    return cast(User, session.user)


def admin_required(user) -> tuple[dict[str, str], HTTPStatus] | None:
    """Check if user is admin; return error tuple or None."""
    from bgmon_api.models import UserRole

    if user.role != UserRole.ADMIN:
        return ({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
    return None
