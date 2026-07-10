# pyright: reportCallIssue=false
"""Web push service tests."""

import json
from unittest.mock import patch

from bgmon_api.models import PushSubscription
from bgmon_api.services import web_push

WebPushException = web_push.WebPushException


class _Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def _create_subscription(
    db_session,
    user_id: int,
    endpoint: str = "https://push.example.com/send/123",
) -> PushSubscription:
    subscription = PushSubscription(
        user_id=user_id,
        endpoint=endpoint,
        p256dh_key="p256dh",
        auth_key="auth",
    )
    db_session.add(subscription)
    db_session.commit()
    return subscription


def test_push_no_private_key(app, observer_user):
    with (
        app.app_context(),
        patch.object(web_push.Config, "VAPID_PRIVATE_KEY", ""),
        patch.object(web_push, "webpush") as mock_webpush,
    ):
        web_push.send_push_to_user(observer_user.id, "Alarm", "Body")

        mock_webpush.assert_not_called()


def test_push_no_subscriptions(app, observer_user):
    with (
        app.app_context(),
        patch.object(web_push.Config, "VAPID_PRIVATE_KEY", "private"),
        patch.object(web_push.logger, "debug") as mock_debug,
    ):
        web_push.send_push_to_user(observer_user.id, "Alarm", "Body")

        mock_debug.assert_called_once_with("No push subscriptions for user %d", observer_user.id)


def test_push_success(app, db_session, observer_user):
    _create_subscription(db_session, observer_user.id)

    with (
        app.app_context(),
        patch.object(web_push.Config, "VAPID_PRIVATE_KEY", "private"),
        patch.object(web_push.Config, "VAPID_SUBJECT", "alerts@example.com"),
        patch.object(web_push, "webpush") as mock_webpush,
    ):
        web_push.send_push_to_user(observer_user.id, "Alarm", "Body")

        mock_webpush.assert_called_once()
        kwargs = mock_webpush.call_args.kwargs
        assert kwargs["subscription_info"]["endpoint"] == "https://push.example.com/send/123"
        assert kwargs["vapid_private_key"] == "private"
        assert kwargs["vapid_claims"]["sub"] == "mailto:alerts@example.com"
        assert kwargs["vapid_claims"]["aud"] == "https://push.example.com"
        payload = json.loads(kwargs["data"])
        assert payload["title"] == "Alarm"
        assert payload["body"] == "Body"
        assert payload["requireInteraction"] is True


def test_push_expired_subscription_removed(app, db_session, observer_user):
    subscription = _create_subscription(db_session, observer_user.id)
    subscription_id = subscription.id
    expired_error = WebPushException("gone", response=_Response(410))

    with (
        app.app_context(),
        patch.object(web_push.Config, "VAPID_PRIVATE_KEY", "private"),
        patch.object(web_push, "webpush", side_effect=expired_error),
    ):
        web_push.send_push_to_user(observer_user.id, "Alarm", "Body")

        assert db_session.get(PushSubscription, subscription_id) is None


def test_push_non_expired_error_logged(app, db_session, observer_user):
    subscription = _create_subscription(
        db_session,
        observer_user.id,
        endpoint="https://push.example.com/send/456",
    )
    server_error = WebPushException("server error", response=_Response(500))

    with (
        app.app_context(),
        patch.object(web_push.Config, "VAPID_PRIVATE_KEY", "private"),
        patch.object(web_push, "webpush", side_effect=server_error),
        patch.object(web_push.logger, "error") as mock_error,
    ):
        web_push.send_push_to_user(observer_user.id, "Alarm", "Body")

        mock_error.assert_called_once()
        assert db_session.get(PushSubscription, subscription.id) is not None
