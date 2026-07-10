"""Twilio phone call service for critical alarm escalation."""

import logging
import time

from sqlalchemy.exc import SQLAlchemyError
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from bgmon_api.config import Config
from bgmon_api.extensions import db
from bgmon_api.models import Alarm, LogEntry, LogEntryType, TwilioCallLog, User, UserRole
from bgmon_api.utils import transactional_session

logger = logging.getLogger(__name__)


def _get_client() -> Client | None:
    if not Config.TWILIO_ACCOUNT_SID or not Config.TWILIO_AUTH_TOKEN:
        return None
    return Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)


def _log_call(user: User, to_number: str, status: str, title: str, sgv: int | None) -> None:
    """Log a Twilio call attempt in the patient's logbook."""
    patient = User.query.filter_by(role=UserRole.PATIENT).first()
    if not patient:
        return
    sgv_str = f"{sgv} mg/dL" if sgv is not None else "keine Daten"
    note = (
        f"Twilio Anruf an {user.display_name} ({to_number}). "
        f"Status: {status}. Alarm: {title}. {sgv_str}."
    )
    entry = LogEntry(
        user_id=patient.id,
        entry_type=LogEntryType.ALARM,
        value=0,
        unit="",
        notes=note,
    )
    db.session.add(entry)
    with transactional_session():
        pass  # commit handled by context manager


def _log_call_error(
    user: User, to_number: str, status: str, title: str, sgv: int | None
) -> None:
    """Log a failed Twilio call, with error handling."""
    try:
        _log_call(user, to_number, status, title, sgv)
    except SQLAlchemyError:
        db.session.rollback()
        logger.error("Failed to log Twilio call error for user %d", user.id)


def place_call(user: User, sgv: int | None, title: str) -> bool:
    """Place a Twilio voice call with retry on failure.

    Retries up to TWILIO_RETRY_COUNT times with TWILIO_RETRY_DELAY_S
    seconds between attempts. Returns True on first successful call.
    """
    client = _get_client()
    if client is None:
        logger.warning("Twilio not configured, skipping call")
        return False

    if not user.phone_number:
        logger.warning("User %d has no phone number", user.id)
        return False

    from_number = user.twilio_from_number or Config.TWILIO_FROM_NUMBER
    if not from_number:
        logger.warning("No Twilio from_number configured for user %d", user.id)
        return False

    if from_number == user.phone_number:
        logger.warning("Twilio from_number equals phone_number for user %d", user.id)
        return False

    sgv_text = (
        f"Der aktuelle Blutzuckerwert beträgt {sgv} Milligramm pro Deziliter. "
        if sgv is not None
        else ""
    )
    twiml = (
        '<Response><Say voice="alice" language="de-DE">'
        f"{sgv_text}{title}. Bitte überprüfen Sie den Blutzuckerwert des Patienten."
        "</Say></Response>"
    )

    max_retries = Config.TWILIO_RETRY_COUNT
    delay = Config.TWILIO_RETRY_DELAY_S

    for attempt in range(1, max_retries + 1):
        try:
            call = client.calls.create(
                to=user.phone_number,
                from_=from_number,
                twiml=twiml,
            )

            call_status = str(call.status) if call.status else "unknown"
            log = TwilioCallLog(
                alarm_id=None,
                to_number=user.phone_number,
                status=call_status,
                twilio_sid=call.sid,
                retry_count=attempt - 1,
            )
            db.session.add(log)
            _log_call(user, user.phone_number, call_status, title, sgv)
            with transactional_session():
                pass

            logger.info(
                "Twilio call %d/%d to %s (user %d) — %s",
                attempt, max_retries, user.phone_number, user.id, call_status,
            )
            return True

        except (TwilioRestException, SQLAlchemyError) as exc:
            logger.error(
                "Twilio call attempt %d/%d for user %d failed (%s): %s",
                attempt, max_retries, user.id, type(exc).__name__, exc,
            )
            if attempt == max_retries:
                log = TwilioCallLog(
                    alarm_id=None, to_number=user.phone_number, status="failed",
                    retry_count=attempt,
                )
                db.session.add(log)
                _log_call_error(user, user.phone_number, "failed", title, sgv)
                return False
            logger.info("Retrying in %ds...", delay)
            time.sleep(delay)

        except Exception as exc:
            logger.error(
                "Unexpected error in Twilio call for user %d: %s", user.id, exc, exc_info=True,
            )
            log = TwilioCallLog(
                alarm_id=None, to_number=user.phone_number, status="failed",
                retry_count=attempt,
            )
            db.session.add(log)
            _log_call_error(user, user.phone_number, "failed", title, sgv)
            return False

    return False


def call_observer_for_alarm(alarm_id: int, observer_id: int) -> bool:
    """Place a Twilio voice call to an observer for a critical alarm.

    Returns True if the call was initiated successfully.
    """
    observer = User.query.get(observer_id)
    if not observer:
        return False
    alarm = Alarm.query.get(alarm_id)
    sgv = alarm.sgv if alarm else None
    title = f"Alarm {alarm.alarm_type.value}" if alarm else "Alarm"
    return place_call(observer, sgv, title)


def escalate_with_calls(alarm_id: int) -> int:
    """Call all observers with phone numbers for an escalated alarm.

    Returns the number of successfully initiated calls.
    """
    observers = User.query.filter_by(role=UserRole.OBSERVER, is_active=True).all()
    success = 0
    for obs in observers:
        if obs.phone_number and call_observer_for_alarm(alarm_id, obs.id):
            success += 1
    return success
