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
    with (
        app.app_context(),
        patch("bgmon_api.services.alarm_evaluator.send_push_to_user") as mock_push,
        patch("bgmon_api.services.alarm_evaluator.place_call") as mock_call,
    ):
        evaluate_alarms()
    return mock_push, mock_call


def test_critical_low_detected(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    _insert_reading(db_session, 50)
    _evaluate(app)
    alarm = Alarm.query.filter_by(user_id=patient_user.id).one()
    assert alarm.alarm_type == AlarmType.CRITICAL_LOW


def test_low_detected(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    _insert_reading(db_session, 65)
    _evaluate(app)
    alarm = Alarm.query.filter_by(user_id=patient_user.id).one()
    assert alarm.alarm_type == AlarmType.LOW


def test_high_detected(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    _insert_reading(db_session, 200)
    _evaluate(app)
    alarm = Alarm.query.filter_by(user_id=patient_user.id).one()
    assert alarm.alarm_type == AlarmType.HIGH


def test_critical_high_detected(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    _insert_reading(db_session, 260)
    _evaluate(app)
    alarm = Alarm.query.filter_by(user_id=patient_user.id).one()
    assert alarm.alarm_type == AlarmType.CRITICAL_HIGH


def test_normal_not_alarmed(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    _insert_reading(db_session, 120)
    _evaluate(app)
    assert Alarm.query.filter_by(user_id=patient_user.id).count() == 0


def test_boundary_at_threshold_low(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    _insert_reading(db_session, 70)
    _evaluate(app)
    assert Alarm.query.filter_by(user_id=patient_user.id).one().alarm_type == AlarmType.LOW


def test_boundary_at_threshold_high(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    _insert_reading(db_session, 180)
    _evaluate(app)
    assert Alarm.query.filter_by(user_id=patient_user.id).one().alarm_type == AlarmType.HIGH


def test_boundary_at_critical_low(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    _insert_reading(db_session, 54)
    _evaluate(app)
    assert Alarm.query.filter_by(user_id=patient_user.id).one().alarm_type == AlarmType.CRITICAL_LOW


def test_boundary_at_critical_high(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    _insert_reading(db_session, 250)
    _evaluate(app)
    assert (
        Alarm.query.filter_by(user_id=patient_user.id).one().alarm_type
        == AlarmType.CRITICAL_HIGH
    )


def test_push_notification_dispatched(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
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
    db_session.add(
        Threshold(user_id=observer_user.id, critical_low=54, low=70, high=180, critical_high=250)
    )
    _create_profile(db_session, observer_user.id, {"critical_low": "call"})
    _insert_reading(db_session, 50)
    mock_push, mock_call = _evaluate(app)
    mock_push.assert_not_called()
    mock_call.assert_not_called()
    assert (
        Alarm.query.filter_by(user_id=observer_user.id).one().alarm_type
        == AlarmType.CRITICAL_LOW
    )


def test_deactivated_profile_skipped(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    notification_profile_with_assignments.is_active = False
    db_session.commit()
    _insert_reading(db_session, 50)
    mock_push, mock_call = _evaluate(app)
    mock_push.assert_not_called()
    mock_call.assert_not_called()
    assert Alarm.query.filter_by(user_id=patient_user.id).one().alarm_type == AlarmType.CRITICAL_LOW


def test_snoozed_alarm_not_repeated(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
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


def test_snooze_broken_on_level_change(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
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


def test_snooze_set_after_dispatch(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
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
    assert snooze is not None and snooze.reason == "alarm:no_data"
    assert snooze.snooze_until > datetime.now(UTC)


def test_no_data_dispatched_via_profile_assignment(
    app, db_session, patient_user, notification_profile_with_assignments
):
    mock_push, mock_call = _evaluate(app)
    mock_call.assert_not_called()
    assert mock_push.call_count == 1
    called_user, called_title, _called_body = mock_push.call_args.args
    assert (called_user, called_title) == (patient_user.id, "Keine Daten")


def test_no_data_fires_when_reading_stale(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    _insert_reading(db_session, 120, minutes_ago=30)
    mock_push, mock_call = _evaluate(app)
    alarm = Alarm.query.filter_by(user_id=patient_user.id).one()
    assert alarm.alarm_type == AlarmType.NO_DATA
    assert alarm.acknowledged_at is None
    mock_push.assert_called_once()
    mock_call.assert_not_called()


def test_no_data_not_fired_within_stale_threshold(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    _insert_reading(db_session, 120, minutes_ago=5)
    mock_push, mock_call = _evaluate(app)
    assert Alarm.query.filter_by(user_id=patient_user.id).count() == 0
    mock_push.assert_not_called()
    mock_call.assert_not_called()


def test_no_data_custom_stale_threshold(app, db_session, patient_user, thresholds):
    thresholds.no_data_after_minutes = 60
    db_session.commit()
    _create_profile(db_session, patient_user.id, {"no_data": "push"})
    _insert_reading(db_session, 120, minutes_ago=30)
    mock_push, mock_call = _evaluate(app)
    assert Alarm.query.filter_by(user_id=patient_user.id).count() == 0
    mock_push.assert_not_called()
    mock_call.assert_not_called()

    db_session.query(GlucoseReading).delete()
    db_session.commit()
    _insert_reading(db_session, 120, minutes_ago=90)
    mock_push, mock_call = _evaluate(app)
    alarm = Alarm.query.filter_by(user_id=patient_user.id).one()
    assert alarm.alarm_type == AlarmType.NO_DATA
    mock_push.assert_called_once()


def test_no_data_alarm_resolved_when_fresh_data_returns(
    app, db_session, patient_user, notification_profile_with_assignments
):
    _evaluate(app)
    alarm = Alarm.query.filter_by(user_id=patient_user.id).one()
    assert alarm.acknowledged_at is None
    _insert_reading(db_session, 120)
    _evaluate(app)
    alarm = db_session.get(Alarm, alarm.id)
    assert alarm.acknowledged_at is not None


def test_no_data_without_assignment_skips_dispatch(
    app, db_session, patient_user, thresholds
):
    _create_profile(db_session, patient_user.id, {"low": "push"})
    mock_push, mock_call = _evaluate(app)
    mock_push.assert_not_called()
    mock_call.assert_not_called()
    assert Alarm.query.filter_by(user_id=patient_user.id).one().alarm_type == AlarmType.NO_DATA
    assert UserSnooze.query.get(patient_user.id) is None


def test_alarm_resolved_when_glucose_normalizes(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    db_session.add(Alarm(user_id=patient_user.id, alarm_type=AlarmType.CRITICAL_LOW, sgv=50))
    db_session.commit()
    _insert_reading(db_session, 120)
    _evaluate(app)
    alarm = Alarm.query.filter_by(user_id=patient_user.id).one()
    assert alarm.acknowledged_at is not None


def test_escalation_count_increments(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
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


def test_night_profile_adjusts_thresholds(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments, night_profile
):
    _insert_reading(db_session, 65)
    with (
        app.app_context(),
        patch("bgmon_api.services.alarm_evaluator._is_night_time", return_value=True),
        patch("bgmon_api.services.alarm_evaluator.send_push_to_user") as mock_push,
        patch("bgmon_api.services.alarm_evaluator.place_call") as mock_call,
    ):
        evaluate_alarms()
    mock_push.assert_not_called()
    mock_call.assert_not_called()
    assert Alarm.query.filter_by(user_id=patient_user.id).count() == 0


def _evaluate_at(app, local_now):
    with (
        app.app_context(),
        patch("bgmon_api.services.alarm_evaluator.send_push_to_user") as mock_push,
        patch("bgmon_api.services.alarm_evaluator.place_call") as mock_call,
        patch(
            "bgmon_api.services.alarm_evaluator._local_now",
            return_value=local_now,
        ),
    ):
        evaluate_alarms()
    return mock_push, mock_call


def _basal_alarms(patient_id: int) -> list[Alarm]:
    return (
        Alarm.query
        .filter_by(user_id=patient_id, alarm_type=AlarmType.NO_BASAL)
        .order_by(Alarm.id)
        .all()
    )


def _set_reminder(db_session, threshold, value: str | None) -> None:
    threshold.basal_reminder_time = value
    db_session.commit()


def test_basal_reminder_fires_when_no_basal_logged(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    from zoneinfo import ZoneInfo

    from bgmon_api.models import LogEntry, LogEntryType

    _set_reminder(db_session, thresholds, "08:00")
    # Profile must route the new threshold.
    profile = NotificationProfile.query.filter_by(user_id=patient_user.id).one()
    db_session.add(
        NotificationAssignment(
            profile_id=profile.id,
            threshold=NotificationThreshold.NO_BASAL,
            area=NotificationArea.PUSH,
        )
    )
    db_session.commit()

    local_now = datetime.now(UTC).astimezone(ZoneInfo("Europe/Berlin")).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    # Yesterday's basal entry must not satisfy today's reminder.
    db_session.add(
        LogEntry(
            user_id=patient_user.id,
            entry_type=LogEntryType.BASAL,
            value=18,
            unit="U",
            created_at=local_now.astimezone(UTC) - timedelta(days=1),
        )
    )
    db_session.commit()
    _insert_reading(db_session, 120)

    mock_push, _ = _evaluate_at(app, local_now)

    alarms = _basal_alarms(patient_user.id)
    assert len(alarms) == 1
    assert "Basal nicht geloggt" in [c.args[1] for c in mock_push.call_args_list][0]


def test_basal_reminder_waits_for_the_configured_time(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    from zoneinfo import ZoneInfo

    _set_reminder(db_session, thresholds, "18:00")
    _insert_reading(db_session, 120)

    local_now = datetime.now(UTC).astimezone(ZoneInfo("Europe/Berlin")).replace(
        hour=17, minute=30, second=0, microsecond=0
    )
    mock_push, _ = _evaluate_at(app, local_now)

    assert _basal_alarms(patient_user.id) == []
    assert all("Basal" not in str(c.args) for c in mock_push.call_args_list)


def test_basal_reminder_silent_when_basal_already_logged(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    from zoneinfo import ZoneInfo

    from bgmon_api.models import LogEntry, LogEntryType

    _set_reminder(db_session, thresholds, "08:00")
    local_now = datetime.now(UTC).astimezone(ZoneInfo("Europe/Berlin")).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    db_session.add(
        LogEntry(
            user_id=patient_user.id,
            entry_type=LogEntryType.BASAL,
            value=18,
            unit="U",
            created_at=local_now.astimezone(UTC),
        )
    )
    db_session.commit()
    _insert_reading(db_session, 120)

    _evaluate_at(app, local_now)

    assert _basal_alarms(patient_user.id) == []


def test_basal_reminder_resolves_after_the_dose_is_logged(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    from zoneinfo import ZoneInfo

    from bgmon_api.models import LogEntry, LogEntryType

    _set_reminder(db_session, thresholds, "08:00")
    local_now = datetime.now(UTC).astimezone(ZoneInfo("Europe/Berlin")).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    _insert_reading(db_session, 120)
    _evaluate_at(app, local_now)
    assert _basal_alarms(patient_user.id)[0].acknowledged_at is None

    db_session.add(
        LogEntry(
            user_id=patient_user.id,
            entry_type=LogEntryType.BASAL,
            value=18,
            unit="U",
            created_at=local_now.astimezone(UTC),
        )
    )
    db_session.commit()
    _evaluate_at(app, local_now)

    assert _basal_alarms(patient_user.id)[0].acknowledged_at is not None


def test_basal_reminder_fires_once_per_day(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    from zoneinfo import ZoneInfo

    from bgmon_api.models import UserSnooze

    _set_reminder(db_session, thresholds, "08:00")
    local_now = datetime.now(UTC).astimezone(ZoneInfo("Europe/Berlin")).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    _insert_reading(db_session, 120)
    _evaluate_at(app, local_now)
    # Drop the snooze so only the once-per-day guard can prevent a repeat.
    UserSnooze.query.filter_by(user_id=patient_user.id).delete()
    db_session.commit()
    _evaluate_at(app, local_now)

    assert len(_basal_alarms(patient_user.id)) == 1


def test_basal_reminder_rolls_over_to_the_next_day(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    from zoneinfo import ZoneInfo

    from bgmon_api.models import UserSnooze

    _set_reminder(db_session, thresholds, "08:00")
    yesterday = datetime.now(UTC).astimezone(ZoneInfo("Europe/Berlin")).replace(
        hour=9, minute=0, second=0, microsecond=0
    ) - timedelta(days=1)
    _insert_reading(db_session, 120)
    _evaluate_at(app, yesterday)
    UserSnooze.query.filter_by(user_id=patient_user.id).delete()
    # The row is stamped by the DB clock, so backdate it to yesterday.
    _basal_alarms(patient_user.id)[0].created_at = yesterday.astimezone(UTC)
    db_session.commit()

    today = yesterday + timedelta(days=1)
    _evaluate_at(app, today)

    alarms = _basal_alarms(patient_user.id)
    assert len(alarms) == 2
    assert alarms[0].acknowledged_at is not None
    assert alarms[1].acknowledged_at is None


def test_basal_reminder_disabled_without_time(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    from zoneinfo import ZoneInfo

    _set_reminder(db_session, thresholds, None)
    local_now = datetime.now(UTC).astimezone(ZoneInfo("Europe/Berlin")).replace(
        hour=23, minute=0, second=0, microsecond=0
    )
    _insert_reading(db_session, 120)

    _evaluate_at(app, local_now)

    assert _basal_alarms(patient_user.id) == []


def test_basal_reminder_routes_to_call_when_profile_says_so(
    app, db_session, patient_user, observer_user, thresholds
):
    from zoneinfo import ZoneInfo

    _insert_reading(db_session, 120)
    _set_reminder(db_session, thresholds, "08:00")
    observer_user.phone_number = "+4915112345678"
    db_session.commit()
    # The reminder runs for the profile owner, so give the observer a profile.
    from bgmon_api.models import Threshold as ThresholdModel

    db_session.add(ThresholdModel(user_id=observer_user.id, basal_reminder_time="08:00"))
    db_session.commit()
    _create_profile(db_session, observer_user.id, {"no_basal": "call"})

    local_now = datetime.now(UTC).astimezone(ZoneInfo("Europe/Berlin")).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    mock_push, mock_call = _evaluate_at(app, local_now)

    titles = [c.args[2] for c in mock_call.call_args_list]
    assert "Basal nicht geloggt" in titles


def test_basal_alarm_not_resolved_by_normal_glucose(
    app, db_session, patient_user, thresholds, notification_profile_with_assignments
):
    from zoneinfo import ZoneInfo

    _set_reminder(db_session, thresholds, "08:00")
    local_now = datetime.now(UTC).astimezone(ZoneInfo("Europe/Berlin")).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    _insert_reading(db_session, 120)
    _evaluate_at(app, local_now)

    assert _basal_alarms(patient_user.id)[0].acknowledged_at is None
