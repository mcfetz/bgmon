"""Web Push notification service using pywebpush."""

import json
import logging
from urllib.parse import urlparse

from pywebpush import WebPushException, webpush

from bgmon_api.app import db
from bgmon_api.config import Config
from bgmon_api.models import PushSubscription

logger = logging.getLogger(__name__)


def _vapid_claims() -> dict:
    claims = {"sub": Config.VAPID_SUBJECT}
    if "@" in Config.VAPID_SUBJECT and not Config.VAPID_SUBJECT.startswith("mailto:"):
        claims["sub"] = f"mailto:{Config.VAPID_SUBJECT}"
    return claims


def send_push_to_user(user_id: int, title: str, body: str) -> None:
    """Send a push notification to all subscriptions for a user."""
    if not Config.VAPID_PRIVATE_KEY:
        logger.warning("VAPID private key not configured, skipping push")
        return

    subscriptions = PushSubscription.query.filter_by(user_id=user_id).all()
    if not subscriptions:
        logger.debug("No push subscriptions for user %d", user_id)
        return

    payload = json.dumps({
        "title": title,
        "body": body,
        "icon": "/icon-192.png",
        "badge": "/icon-192.png",
        "tag": "bgmon-alarm",
        "requireInteraction": True,
    })

    base_claims = _vapid_claims()

    for sub in subscriptions:
        parsed = urlparse(sub.endpoint)
        endpoint_origin = f"{parsed.scheme}://{parsed.netloc}"
        claims_with_aud = {**base_claims, "aud": endpoint_origin}

        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh_key,
                        "auth": sub.auth_key,
                    },
                },
                data=payload,
                vapid_private_key=Config.VAPID_PRIVATE_KEY,
                vapid_claims=claims_with_aud,
            )
            logger.debug("Push sent to %s", sub.endpoint[:60])
        except WebPushException as exc:
            if exc.response and exc.response.status_code in (404, 410):
                logger.info("Removing expired push subscription for user %d", user_id)
                db.session.delete(sub)
                db.session.commit()
            else:
                logger.error("Push failed for user %d: %s", user_id, exc)
