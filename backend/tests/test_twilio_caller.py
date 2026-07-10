# pyright: reportCallIssue=false
"""Twilio caller service tests."""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

from bgmon_api.models import Alarm, AlarmType, LogEntry, TwilioCallLog, User
from bgmon_api.services import twilio_caller

TwilioRestException = twilio_caller.TwilioRestException


def _user_id_by_email(db_session, email: str) -> int:
    return db_session.query(User).filter_by(email=email).one().id


def _create_alarm(db_session, user_id: int, sgv: int = 55) -> Alarm:
    alarm = Alarm(
        user_id=user_id,
        alarm_type=AlarmType.CRITICAL_LOW,
        sgv=sgv,
        created_at=datetime.now(UTC),
    )
    db_session.add(alarm)
    db_session.commit()
    return alarm


def test_get_client_no_credentials():
    with (
        patch.object(twilio_caller.Config, "TWILIO_ACCOUNT_SID", ""),
        patch.object(twilio_caller.Config, "TWILIO_AUTH_TOKEN", "token"),
    ):
        assert twilio_caller._get_client() is None


def test_place_call_no_phone_number(app, patient_user):
    with (
        app.app_context(),
        patch.object(twilio_caller.Config, "TWILIO_ACCOUNT_SID", "sid"),
        patch.object(twilio_caller.Config, "TWILIO_AUTH_TOKEN", "token"),
        patch.object(twilio_caller, "Client") as mock_client,
    ):
        patient_user.phone_number = None

        assert twilio_caller.place_call(patient_user, 72, "Alarm") is False
        mock_client.return_value.calls.create.assert_not_called()


def test_place_call_no_from_number(app, observer_user):
    with (
        app.app_context(),
        patch.object(twilio_caller.Config, "TWILIO_ACCOUNT_SID", "sid"),
        patch.object(twilio_caller.Config, "TWILIO_AUTH_TOKEN", "token"),
        patch.object(twilio_caller.Config, "TWILIO_FROM_NUMBER", ""),
        patch.object(twilio_caller, "Client") as mock_client,
    ):
        observer_user.twilio_from_number = None

        assert twilio_caller.place_call(observer_user, 72, "Alarm") is False
        mock_client.return_value.calls.create.assert_not_called()


def test_place_call_self_call_prevented(app, observer_user):
    with (
        app.app_context(),
        patch.object(twilio_caller.Config, "TWILIO_ACCOUNT_SID", "sid"),
        patch.object(twilio_caller.Config, "TWILIO_AUTH_TOKEN", "token"),
        patch.object(twilio_caller.Config, "TWILIO_FROM_NUMBER", observer_user.phone_number),
        patch.object(twilio_caller, "Client") as mock_client,
    ):
        observer_user.twilio_from_number = None

        assert twilio_caller.place_call(observer_user, 72, "Alarm") is False
        mock_client.return_value.calls.create.assert_not_called()


def test_place_call_success(app, db_session, patient_user, observer_user):
    assert patient_user.id is not None
    assert observer_user.id is not None
    patient_id = _user_id_by_email(db_session, "patient@example.com")
    observer_id = _user_id_by_email(db_session, "observer@example.com")
    call = Mock(status="queued", sid="CA123")
    client = Mock()
    client.calls.create.return_value = call

    with (
        app.app_context(),
        patch.object(twilio_caller.Config, "TWILIO_ACCOUNT_SID", "sid"),
        patch.object(twilio_caller.Config, "TWILIO_AUTH_TOKEN", "token"),
        patch.object(twilio_caller.Config, "TWILIO_FROM_NUMBER", "+49999999999"),
        patch.object(twilio_caller, "Client", return_value=client),
    ):
        observer = db_session.get(User, observer_id)
        result = twilio_caller.place_call(observer, 48, "Kritisch niedrig")

        assert result is True
        client.calls.create.assert_called_once()
        kwargs = client.calls.create.call_args.kwargs
        assert kwargs["to"] == observer.phone_number
        assert kwargs["from_"] == "+49999999999"
        assert "48 Milligramm pro Deziliter" in kwargs["twiml"]

        call_log = db_session.query(TwilioCallLog).one()
        assert call_log.status == "queued"
        assert call_log.twilio_sid == "CA123"

        patient_logs = db_session.query(LogEntry).filter_by(user_id=patient_id).all()
        assert len(patient_logs) == 1
        assert observer.display_name in (patient_logs[0].notes or "")
        assert "Kritisch niedrig" in (patient_logs[0].notes or "")


def test_place_call_twilio_rest_exception(app, db_session, patient_user, observer_user):
    assert patient_user.id is not None
    assert observer_user.id is not None
    patient_id = _user_id_by_email(db_session, "patient@example.com")
    observer_id = _user_id_by_email(db_session, "observer@example.com")
    client = Mock()
    client.calls.create.side_effect = twilio_caller.TwilioRestException(
        status=500,
        uri="/Calls",
        msg="boom",
        method="POST",
    )

    with (
        app.app_context(),
        patch.object(twilio_caller.Config, "TWILIO_ACCOUNT_SID", "sid"),
        patch.object(twilio_caller.Config, "TWILIO_AUTH_TOKEN", "token"),
        patch.object(twilio_caller.Config, "TWILIO_FROM_NUMBER", "+49999999999"),
        patch.object(twilio_caller, "Client", return_value=client),
    ):
        observer = db_session.get(User, observer_id)
        result = twilio_caller.place_call(observer, 48, "Kritisch niedrig")

        assert result is False
        call_log = db_session.query(TwilioCallLog).one()
        assert call_log.status == "failed"
        assert call_log.twilio_sid is None

        patient_logs = db_session.query(LogEntry).filter_by(user_id=patient_id).all()
        assert len(patient_logs) == 1
        assert "Status: failed" in (patient_logs[0].notes or "")


def test_call_observer_for_alarm(app, db_session, patient_user, observer_user):
    assert patient_user.id is not None
    assert observer_user.id is not None
    patient_id = _user_id_by_email(db_session, "patient@example.com")
    observer_id = _user_id_by_email(db_session, "observer@example.com")
    alarm = _create_alarm(db_session, patient_id, 52)

    with app.app_context(), patch.object(
        twilio_caller, "place_call", return_value=True
    ) as mock_place_call:
        result = twilio_caller.call_observer_for_alarm(alarm.id, observer_id)

        assert result is True
        called_user, called_sgv, called_title = mock_place_call.call_args.args
        assert called_user.id == observer_id
        assert called_sgv == 52
        assert called_title == "Alarm critical_low"


def test_escalate_with_calls(app, db_session, patient_user, observer_user):
    assert patient_user.id is not None
    assert observer_user.id is not None
    patient_id = _user_id_by_email(db_session, "patient@example.com")
    observer_id = _user_id_by_email(db_session, "observer@example.com")
    observer_role = db_session.get(User, observer_id).role
    silent_observer = User(
        email="silent@example.com",
        display_name="Silent Observer",
        role=observer_role,
        phone_number=None,
        is_active=True,
    )
    silent_observer.set_password("test_password")
    second_observer = User(
        email="second@example.com",
        display_name="Second Observer",
        role=observer_role,
        phone_number="+49111111111",
        is_active=True,
    )
    second_observer.set_password("test_password")
    db_session.add_all([silent_observer, second_observer])
    db_session.commit()
    second_observer_id = second_observer.id
    alarm = _create_alarm(db_session, patient_id)

    with app.app_context(), patch.object(
        twilio_caller, "call_observer_for_alarm", side_effect=[True, True]
    ) as mock_call_observer:
        result = twilio_caller.escalate_with_calls(alarm.id)

        assert result == 2
        called_observer_ids = [call.args[1] for call in mock_call_observer.call_args_list]
        assert called_observer_ids == [observer_id, second_observer_id]
