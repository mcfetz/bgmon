"""Tests for insulin stock tracking — usage estimate and low-stock alert."""

import pytest

from bgmon_api.models import LogEntry, LogEntryType
from bgmon_api.services.insulin_stock import (
    compute_status,
    days_left,
    estimate_daily_usage,
    evaluate_low_stock,
)


def _log(db_session, user_id, minutes_ago, value, unit="U"):
    from datetime import UTC, datetime, timedelta

    db_session.add(
        LogEntry(
            user_id=user_id,
            entry_type=LogEntryType.INSULIN,
            value=value,
            unit=unit,
            created_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        )
    )


def test_days_left_math():
    assert days_left(1000, 50.0) == 20.0
    assert days_left(None, 50.0) is None
    assert days_left(1000, 0) is None


def test_estimate_daily_usage_counts_priming_per_injection(db_session, patient_user):
    _log(db_session, patient_user.id, minutes_ago=5, value=5)
    _log(db_session, patient_user.id, minutes_ago=60, value=5)
    db_session.commit()

    usage = estimate_daily_usage(days=1)
    assert usage["active_days"] == 1
    assert usage["avg_daily_units"] == 10.0
    assert usage["avg_daily_injections"] == 2.0
    assert usage["usage_per_day"] == 12.0


def test_compute_status_when_not_configured(db_session, global_settings):
    global_settings.insulin_stock = None
    db_session.commit()

    status = compute_status()
    assert status["configured"] is False
    assert status["low_stock"] is False
    assert status["days_left"] is None


def test_compute_status_with_low_stock(db_session, patient_user, global_settings):
    global_settings.insulin_stock = 20.0
    global_settings.low_stock_days = 30
    db_session.commit()
    _log(db_session, patient_user.id, minutes_ago=5, value=5)
    _log(db_session, patient_user.id, minutes_ago=60, value=5)
    db_session.commit()

    status = compute_status()
    assert status["configured"] is True
    assert status["usage_per_day"] == pytest.approx(0.9)
    assert status["days_left"] == pytest.approx(22.2)
    assert status["low_stock"] is True


def test_compute_status_with_sufficient_stock(db_session, patient_user, global_settings):
    global_settings.insulin_stock = 1000.0
    db_session.commit()
    _log(db_session, patient_user.id, minutes_ago=5, value=5)
    _log(db_session, patient_user.id, minutes_ago=60, value=5)
    db_session.commit()

    assert compute_status()["low_stock"] is False


def test_evaluate_low_stock_logs_smart_alert_and_obeys_cooldown(
    db_session, patient_user, global_settings
):
    global_settings.insulin_stock = 20.0
    global_settings.low_stock_days = 30
    db_session.commit()
    _log(db_session, patient_user.id, minutes_ago=5, value=5)
    _log(db_session, patient_user.id, minutes_ago=60, value=5)
    db_session.commit()

    result = evaluate_low_stock()
    assert result is not None
    assert result["low_stock"] is True

    note = (
        LogEntry.query
        .filter(
            LogEntry.user_id == patient_user.id,
            LogEntry.entry_type == LogEntryType.NOTE,
        )
        .first()
    )
    assert note is not None
    assert "SmartAlert:insulin_low_stock:" in (note.notes or "")

    assert evaluate_low_stock() is None


def test_evaluate_low_stock_skips_when_no_stock_configured(
    db_session, global_settings
):
    global_settings.insulin_stock = None
    db_session.commit()

    assert evaluate_low_stock() is None


def test_to_dict_includes_insulin_stock_fields(global_settings):
    data = global_settings.to_dict()
    assert "insulin_stock" in data
    assert data["low_stock_days"] == 14
    assert data["insulin_low_stock_cooldown_minutes"] == 1440
