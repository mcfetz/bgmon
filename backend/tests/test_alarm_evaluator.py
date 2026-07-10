# pyright: reportCallIssue=false
"""Alarm evaluator service tests."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from bgmon_api.models import (
    Alarm,
    AlarmType,
    GlucoseReading,
    NotificationArea,
    NotificationAssignment,
    NotificationProfile,
    NotificationThreshold,
    Threshold,
    UserActiveProfile,
    UserSnooze,
)
from bgmon_api.services.alarm_evaluator import evaluate_alarms


def _insert_reading(db_session, sgv: int, *, minutes_ago: int = 1) -> GlucoseReading:
    reading = GlucoseReading(
        timestamp=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        sgv=sgv,
        trend=4,
        direction="Flat",
        source="test",
    )
    db_session.add(reading)
    db_session.commit()
    return reading


def _create_profile(db_session, user_id: int, areas: dict[str, str]) -> NotificationProfile:
    profile = NotificationProfile(user_id=user_id, name="Test", icon="bell", is_active=True)
    db_session.add(profile)
    db_session.flush()
    for threshold, area in areas.items():
        db_session.add(
            NotificationAssignment(
                profile_id=profile.id,
                threshold=NotificationThreshold(threshold),
                area=NotificationArea(area),
            )
        )
    db_session.add(UserActiveProfile(user_id=user_id, profile_id=profile.id))
    db_session.commit()
    return profile


def _evaluate(app):
    with app.app_context():
        with (
            patch("bgmon_api.services.alarm_evaluator.send_push_to_user") as mock_push,
            patch("bgmon_api.services.alarm_evaluator.place_call") as mock_call,
        ):
            evaluate_alarms()
    return mock_push, mock_call


def test_critical_low_detected(app, db_session, patient_user, thresholds, notification_profile_with_assignments):
    _insert_reading(db_session, 50)
    _evaluate(app)
    alarm = Alarm.query.filter_by(user_id=patient_user.id).one()
    assert alarm.alarm_type == AlarmType.CRITICAL_LOW


def test_low_detected(app, db_session, patient_user, thresholds, notification_profile_with_assignments):
    _insert_reading(db_session, 65)
    _evaluate(app)
    alarm = Alarm.query.filter_by(user_id=patient_user.id).one()
    assert alarm.alarm_type == AlarmType.LOW


def test_high_detected(app, db_session, patient_user, thresholds, notification_profile_with_assignments):
    _insert_reading(db_session, 200)
    _evaluate(app)
    alarm = Alarm.query.filter_by(user_id=patient_user.id).one()
    assert alarm.alarm_type == AlarmType.HIGH


def test_critical_high_detected(app, db_session, patient_user, thresholds, notification_profile_with_assignments):
    _insert_reading(db_session, 260)
    _evaluate(app)
    alarm = Alarm.query.filter_by(user_id=patient_user.id).one()
    assert alarm.alarm_type == AlarmType.CRITICAL_HIGH


def test_normal_not_alarmed(app, db_session, patient_user, thresholds, notification_profile_with_assignments):
    _insert_reading(db_session, 120)
    _evaluate(app)
    assert Alarm.query.filter_by(user_id=patient_user.id).count() == 0


def test_boundary_at_threshold_low(app, db_session, patient_user, thresholds, notification_profile_with_assignments):
    _insert_reading(db_session, 70)
    _evaluate(app)
    assert Alarm.query.filter_by(user_id=patient_user.id).one().alarm_type == AlarmType.LOW


def test_boundary_at_threshold_high(app, db_session, patient_user, thresholds, notification_profile_with_assignments):
    _insert_reading(db_session, 180)
    _evaluate(app)
    assert Alarm.query.filter_by(user_id=patient_user.id).one().alarm_type == AlarmType.HIGH


def test_boundary_at_critical_low(app, db_session, patient_user, thresholds, notification_profile_with_assignments):
    _insert_reading(db_session, 54)
    _evaluate(app)
    assert Alarm.query.filter_by(user_id=patient_user.id).one().alarm_type == AlarmType.CRITICAL_LOW


def test_boundary_at_critical_high(app, db_session, patient_user, thresholds, notification_profile_with_assignments):
    _insert_reading(db_session, 250)
    _evaluate(app)
    assert Alarm.query.filter_by(user_id=patient_user.id).one().alarm_type == AlarmType.CRITICAL_HIGH


def test_push_notification_dispatched(app, db_session, patient_user, thresholds, notification_profile_with_assignments):
    _insert_reading(db_session, 65)
    mock_push, mock_call = _evaluate(app)
    mock_push.assert_called_once_with(patient_user.id, "Niedrig", "Aktueller Wert: 65 mg/dL")
    mock_call.assert_not_called()


def test_call_notification_dispatched(app, db_session, patient_user, thresholds):
    patient_user.phone_number = "+49123456789"
    db_session.commit()
    _create_profile(db_session, patient_user.id, {"critical_low": "call"})
    _insert_reading(db_session, 50)
    mock_push, mock_call = _evaluate(app)
    mock_call.assert_called_once()
    _called_user, called_sgv, called_title = mock_call.call_args.args
    assert (called_sgv, called_title) == (50, "Kritisch niedrig")
    mock_push.assert_not_called()


def test_call_fallback_when_no_phone(app, db_session, observer_user):
    observer_user.phone_number = None
    db_session.add(observer_user)
    db_session.add(Threshold(user_id=observer_user.id, critical_low=54, low=70, high=180, critical_high=250))
    _create_profile(db_session, observer_user.id, {"critical_low": "call"})
    _insert_reading(db_session, 50)
    mock_push, mock_call = _evaluate(app)
    mock_push.assert_not_called()
    mock_call.assert_not_called()
    assert Alarm.query.filter_by(user_id=observer_user.id).one().alarm_type == AlarmType.CRITICAL_LOW


def test_deactivated_profile_skipped(app, db_session, patient_user, thresholds, notification_profile_with_assignments):
    notification_profile_with_assignments.is_active = False
    db_session.commit()
    _insert_reading(db_session, 50)
    mock_push, mock_call = _evaluate(app)
    mock_push.assert_not_called()
    mock_call.assert_not_called()
    assert Alarm.query.filter_by(user_id=patient_user.id).one().alarm_type == AlarmType.CRITICAL_LOW


def test_snoozed_alarm_not_repeated(app, db_session, patient_user, thresholds, notification_profile_with_assignments):
    db_session.add(
        UserSnooze(
            user_id=patient_user.id,
            snooze_until=datetime.now(UTC) + timedelta(minutes=15),
            reason="alarm:low",
        )
    )
    db_session.commit()
    _insert_reading(db_session, 65)
    mock_push, mock_call = _evaluate(app)
    mock_push.assert_not_called()
    mock_call.assert_not_called()


def test_snooze_broken_on_level_change(app, db_session, patient_user, thresholds, notification_profile_with_assignments):
    db_session.add(
        UserSnooze(
            user_id=patient_user.id,
            snooze_until=datetime.now(UTC) + timedelta(minutes=15),
            reason="alarm:low",
        )
    )
    db_session.commit()
    _insert_reading(db_session, 50)
    mock_push, _mock_call = _evaluate(app)
    snooze = UserSnooze.query.get(patient_user.id)
    mock_push.assert_called_once()
    assert snooze is not None and snooze.reason == "alarm:critical_low"


def test_snooze_set_after_dispatch(app, db_session, patient_user, thresholds, notification_profile_with_assignments):
    _insert_reading(db_session, 65)
    _evaluate(app)
    snooze = UserSnooze.query.get(patient_user.id)
    assert snooze is not None and snooze.reason == "alarm:low"
    assert snooze.snooze_until > datetime.now(UTC)


def test_no_data_alarm_when_empty(app, patient_user, notification_profile_with_assignments):
    _evaluate(app)
    alarm = Alarm.query.filter_by(user_id=patient_user.id).one()
    assert alarm.alarm_type == AlarmType.NO_DATA


def test_no_data_sets_snooze(app, patient_user, notification_profile_with_assignments):
    _evaluate(app)
    snooze = UserSnooze.query.get(patient_user.id)
    assert snooze is not None and snooze.reason == "no_data"
    assert snooze.snooze_until > datetime.now(UTC)


def test_alarm_resolved_when_glucose_normalizes(app, db_session, patient_user, thresholds, notification_profile_with_assignments):
    db_session.add(Alarm(user_id=patient_user.id, alarm_type=AlarmType.CRITICAL_LOW, sgv=50))
    db_session.commit()
    _insert_reading(db_session, 120)
    _evaluate(app)
    alarm = Alarm.query.filter_by(user_id=patient_user.id).one()
    assert alarm.acknowledged_at is not None


def test_escalation_count_increments(app, db_session, patient_user, thresholds, notification_profile_with_assignments):
    db_session.add(
        Alarm(
            user_id=patient_user.id,
            alarm_type=AlarmType.LOW,
            sgv=65,
            created_at=datetime.now(UTC) - timedelta(minutes=10),
        )
    )
    db_session.commit()
    _insert_reading(db_session, 65)
    _evaluate(app)
    alarm = Alarm.query.filter_by(user_id=patient_user.id).one()
    assert alarm.escalation_count == 1


def test_night_profile_adjusts_thresholds(app, db_session, patient_user, thresholds, notification_profile_with_assignments, night_profile):
    _insert_reading(db_session, 65)
    with app.app_context(), patch("bgmon_api.services.alarm_evaluator._is_night_time", return_value=True), patch(
        "bgmon_api.services.alarm_evaluator.send_push_to_user"
    ) as mock_push, patch("bgmon_api.services.alarm_evaluator.place_call") as mock_call:
        evaluate_alarms()
    mock_push.assert_not_called()
    mock_call.assert_not_called()
    assert Alarm.query.filter_by(user_id=patient_user.id).count() == 0
