"""Alarm evaluator — runs periodically to check glucose thresholds."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy.exc import SQLAlchemyError

from bgmon_api.extensions import db
from bgmon_api.services.influx_reader import query_current_glucose as query_influx
from bgmon_api.services.twilio_caller import place_call
from bgmon_api.services.web_push import send_push_to_user
from bgmon_api.utils import transactional_session

if TYPE_CHECKING:
    from bgmon_api.models import AlarmType, NightProfile, User

logger = logging.getLogger(__name__)

SNOOZE_DURATION = timedelta(minutes=15)


def _models():
    """Lazy import to avoid circular imports."""
    from bgmon_api.models import (
        Alarm,
        AlarmType,
        LogEntry,
        LogEntryType,
        NightProfile,
        NotificationAssignment,
        NotificationProfile,
        NotificationThreshold,
        Threshold,
        User,
        UserActiveProfile,
        UserRole,
        UserSnooze,
    )
    return {
        "Alarm": Alarm,
        "AlarmType": AlarmType,
        "LogEntry": LogEntry,
        "LogEntryType": LogEntryType,
        "NightProfile": NightProfile,
        "NotificationAssignment": NotificationAssignment,
        "NotificationProfile": NotificationProfile,
        "NotificationThreshold": NotificationThreshold,
        "Threshold": Threshold,
        "User": User,
        "UserActiveProfile": UserActiveProfile,
        "UserRole": UserRole,
        "UserSnooze": UserSnooze,
    }


def _query_current_glucose() -> dict | None:
    """Get current glucose from InfluxDB, fallback to PostgreSQL."""
    result = query_influx()
    if result is not None:
        return result
    logger.warning("InfluxDB unavailable, falling back to PostgreSQL")
    try:
        from bgmon_api.models import GlucoseReading
        row = (
            GlucoseReading.query
            .order_by(GlucoseReading.timestamp.desc())
            .first()
        )
        if row is not None:
            return {
                "sgv": row.sgv,
                "trend": row.trend,
                "direction": row.direction,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            }
    except SQLAlchemyError as exc:
        logger.exception("PostgreSQL fallback query failed: %s", exc)
    except (AttributeError, ValueError) as exc:
        logger.exception("Error processing glucose reading: %s", exc)
    return None


def evaluate_alarms() -> None:
    """Check glucose against each user's thresholds and dispatch notifications."""
    m = _models()
    logger.info("evaluate_alarms() called")
    current = _query_current_glucose()
    logger.info("Glucose query result: %s", current)
    if current is None:
        logger.info("No glucose data available for alarm evaluation")
        _check_no_data_alarm()
        return

    sgv = current.get("sgv")
    if sgv is None:
        logger.info("Current glucose has no SGV value")
        return

    active_profiles = m["UserActiveProfile"].query.all()
    if not active_profiles:
        logger.info("No users have an active notification profile, skipping")
        return

    for active in active_profiles:
        try:
            _evaluate_for_user(active.user_id, sgv)
        except Exception:
            logger.exception("Error evaluating alarms for user %d", active.user_id)
            db.session.rollback()


def _evaluate_for_user(user_id: int, sgv: int) -> None:
    m = _models()

    threshold = m["Threshold"].query.filter_by(user_id=user_id).first()
    if threshold is None:
        threshold = m["Threshold"](user_id=user_id)
        db.session.add(threshold)
        with transactional_session():
            pass  # auto-commit

    active_low = threshold.low
    active_high = threshold.high
    active_critical_low = threshold.critical_low
    active_critical_high = threshold.critical_high

    night_profile = m["NightProfile"].query.filter_by(user_id=user_id).first()
    if night_profile and night_profile.enabled and _is_night_time(night_profile):
        active_low = max(active_low - 10, 60)
        active_high = min(active_high + 10, 200)

    breached = None
    if sgv <= active_critical_low:
        breached = m["NotificationThreshold"].CRITICAL_LOW
    elif sgv <= active_low:
        breached = m["NotificationThreshold"].LOW
    elif sgv >= active_critical_high:
        breached = m["NotificationThreshold"].CRITICAL_HIGH
    elif sgv >= active_high:
        breached = m["NotificationThreshold"].HIGH

    if breached is not None:
        _create_or_update_alarm(user_id, breached, sgv)
        _dispatch_to_user(user_id, breached, sgv)
    else:
        _resolve_open_alarms(user_id)


def _check_no_data_alarm() -> None:
    m = _models()
    patient = m["User"].query.filter_by(role=m["UserRole"].PATIENT).first()
    if patient is None:
        return
    open_no_data = m["Alarm"].query.filter_by(
        user_id=patient.id, alarm_type=m["AlarmType"].NO_DATA, acknowledged_at=None
    ).first()
    if open_no_data is None:
        alarm = m["Alarm"](user_id=patient.id, alarm_type=m["AlarmType"].NO_DATA, sgv=None)
        db.session.add(alarm)
        with transactional_session():
            pass  # auto-commit

    active_profiles = m["UserActiveProfile"].query.all()
    for active in active_profiles:
        _dispatch_to_user(active.user_id, None, None, reason="Keine Daten seit >15 Minuten")


def check_profile_schedules() -> None:
    """Auto-activate profiles whose start_time matches the current minute."""
    from datetime import UTC
    m = _models()
    now = datetime.now(UTC)
    current_hhmm = now.strftime("%H:%M")

    profiles = m["NotificationProfile"].query.filter(
        m["NotificationProfile"].start_time.isnot(None)
    ).all()

    for profile in profiles:
        if profile.start_time.strftime("%H:%M") != current_hhmm:
            continue
        active = m["UserActiveProfile"].query.get(profile.user_id)
        if active and active.profile_id == profile.id:
            continue
        if active:
            active.profile_id = profile.id
        else:
            db.session.add(
                m["UserActiveProfile"](user_id=profile.user_id, profile_id=profile.id)
            )
        logger.info(
            "Auto-activated profile '%s' (id=%d) for user %d (start_time=%s)",
            profile.name, profile.id, profile.user_id, current_hhmm,
        )

    if profiles:
        with transactional_session():
            pass  # auto-commit


def _create_or_update_alarm(user_id: int, threshold, sgv: int) -> None:
    m = _models()
    alarm_type = _threshold_to_alarm_type(threshold)
    open_alarm = (
        m["Alarm"].query.filter_by(user_id=user_id, alarm_type=alarm_type, acknowledged_at=None)
        .order_by(m["Alarm"].created_at.desc())
        .first()
    )
    if open_alarm is not None:
        minutes_since_created = (datetime.now(UTC) - open_alarm.created_at).total_seconds() / 60
        if minutes_since_created > 5 * (open_alarm.escalation_count + 1):
            open_alarm.escalation_count += 1
            with transactional_session():
                pass  # auto-commit
            logger.info(
                "Alarm %d escalated to level %d", open_alarm.id, open_alarm.escalation_count
            )
        return
    alarm = m["Alarm"](user_id=user_id, alarm_type=alarm_type, sgv=sgv)
    db.session.add(alarm)
    with transactional_session():
        pass  # auto-commit


def _resolve_open_alarms(user_id: int) -> None:
    m = _models()
    open_alarms = m["Alarm"].query.filter(
        m["Alarm"].user_id == user_id,
        m["Alarm"].acknowledged_at.is_(None),
        m["Alarm"].alarm_type != m["AlarmType"].NO_DATA,
    ).all()
    for alarm in open_alarms:
        alarm.acknowledged_at = datetime.now(UTC)
    if open_alarms:
        with transactional_session():
            pass  # auto-commit
        logger.info("Resolved %d open alarms for user %d", len(open_alarms), user_id)


def _dispatch_to_user(
    user_id: int, threshold, sgv: int | None, reason: str | None = None
) -> None:
    m = _models()

    current_level = threshold.value if threshold else None

    snooze = m["UserSnooze"].query.get(user_id)
    if snooze and snooze.is_active and current_level:
        snooze_level = (
            snooze.reason.removeprefix("alarm:")
            if snooze.reason and snooze.reason.startswith("alarm:")
            else None
        )
        if snooze_level == current_level:
            snooze_until = getattr(snooze, 'snooze_until', None)
            remaining = ""
            if snooze_until:
                remaining_min = max(0, (snooze_until - datetime.now(UTC)).total_seconds() // 60)
                if snooze_until.tzinfo is None:
                    snooze_until = snooze_until.replace(tzinfo=UTC)
                remaining = (
                    f" (noch {int(remaining_min)} min, "
                    f"bis {snooze_until.strftime('%H:%M')})"
                )
            logger.info(
                "User %d is snoozed at level %s, skipping notification%s",
                user_id, current_level, remaining,
            )
            return
        # Only break snooze if condition WORSENED
        _escalated = {
            "low": {"critical_low"},
            "high": {"critical_high"},
        }
        if current_level not in _escalated.get(snooze_level, set()):
            logger.info(
                "User %d level improved: snoozed=%s, new=%s — keeping snooze",
                user_id, snooze_level, current_level,
            )
            return
        logger.info(
            "User %d level worsened: snoozed=%s, new=%s — breaking snooze",
            user_id, snooze_level, current_level,
        )
        db.session.delete(snooze)
        with transactional_session():
            pass  # auto-commit

    active = m["UserActiveProfile"].query.get(user_id)
    if not active:
        return

    user = m["User"].query.get(user_id)
    if not user:
        return

    if threshold is None:
        if reason:
            _log_notification(user, reason, sgv)
            _set_snooze(user_id, reason="no_data")
        return

    profile = m["NotificationProfile"].query.get(active.profile_id)
    if not profile:
        logger.warning(
            "Active profile %d not found for user %d", active.profile_id, user_id
        )
        return

    if not profile.is_active:
        logger.info("Profile '%s' (user %d) is deactivated, skipping", profile.name, user_id)
        return

    assignment = m["NotificationAssignment"].query.filter_by(
        profile_id=profile.id, threshold=threshold
    ).first()
    if not assignment:
        logger.info(
            "Profile '%s' (user %d) has no assignment for %s, skipping",
            profile.name, user_id, threshold.value,
        )
        return

    area = assignment.area.value
    title = _alarm_title_for(threshold, sgv)

    dispatched = False
    if area == "call":
        dispatched = _dispatch_call(user, title, sgv)
    elif area == "push":
        dispatched = _dispatch_push(user, title, sgv)

    if dispatched:
        _set_snooze(user_id, reason=f"alarm:{threshold.value}")


def _dispatch_call(user: User, title: str, sgv: int | None) -> bool:
    if not user.phone_number:
        logger.warning("User %d has no phone_number, cannot call", user.id)
        return False
    try:
        place_call(user, sgv, title)
        _log_notification(user, title, sgv)
        return True
    except Exception as exc:
        logger.exception("Failed to place call for user %d: %s", user.id, exc)
        return False


def _dispatch_push(user: User, title: str, sgv: int | None) -> bool:
    body = f"Aktueller Wert: {sgv} mg/dL" if sgv is not None else ""
    try:
        send_push_to_user(user.id, title, body)
        _log_notification(user, title, sgv)
        return True
    except Exception:
        return False


def _set_snooze(user_id: int, reason: str | None = None) -> None:
    m = _models()
    snooze = m["UserSnooze"].query.get(user_id) or m["UserSnooze"](user_id=user_id)
    # Use user preference for snooze duration
    user = m["User"].query.get(user_id)
    minutes = getattr(user, 'snooze_default_minutes', 15) or 15
    snooze.snooze_until = datetime.now(UTC) + timedelta(minutes=minutes)
    snooze.reason = reason
    if snooze not in db.session:
        db.session.add(snooze)
    with transactional_session():
        pass  # commit handled by context manager
    logger.info("User %d snoozed until %s", user_id, snooze.snooze_until)


def _log_notification(user: User, title: str, sgv: int | None) -> None:
    m = _models()
    patient = m["User"].query.filter_by(role=m["UserRole"].PATIENT).first()
    if not patient:
        return
    sgv_str = f"{sgv} mg/dL" if sgv is not None else "keine Daten"
    note = f"Push an {user.display_name}. Alarm: {title}. {sgv_str}."
    entry = m["LogEntry"](
        user_id=patient.id,
        entry_type=m["LogEntryType"].ALARM,
        value=0,
        unit="",
        notes=note,
    )
    db.session.add(entry)
    with transactional_session():
        pass  # auto-commit


def _threshold_to_alarm_type(threshold) -> AlarmType:
    m = _models()
    mapping = {
        threshold.CRITICAL_LOW: m["AlarmType"].CRITICAL_LOW,
        threshold.LOW: m["AlarmType"].LOW,
        threshold.HIGH: m["AlarmType"].HIGH,
        threshold.CRITICAL_HIGH: m["AlarmType"].CRITICAL_HIGH,
    }
    return mapping[threshold]


def _alarm_title_for(threshold, _sgv: int | None) -> str:
    return {
        threshold.CRITICAL_LOW: "Kritisch niedrig",
        threshold.LOW: "Niedrig",
        threshold.HIGH: "Hoch",
        threshold.CRITICAL_HIGH: "Kritisch hoch",
    }[threshold]


def _is_night_time(profile: NightProfile) -> bool:
    now = datetime.now(UTC)
    current_time = now.strftime("%H:%M")
    start = profile.start_time
    end = profile.end_time
    if start <= end:
        return start <= current_time <= end
    return current_time >= start or current_time <= end

