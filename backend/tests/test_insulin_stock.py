"""Tests for insulin stock tracking — usage estimate and low-stock alert."""

import pytest

from bgmon_api.models import LogEntry, LogEntryType
from bgmon_api.services.insulin_stock import (
    compute_status,
    days_left,
    estimate_daily_usage,
    evaluate_low_stock,
)


def _log(db_session, user_id, minutes_ago, value, entry_type=LogEntryType.INSULIN):
    from datetime import UTC, datetime, timedelta

    db_session.add(
        LogEntry(
            user_id=user_id,
            entry_type=entry_type,
            value=value,
            unit="U",
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

    usage = estimate_daily_usage(entry_type=LogEntryType.INSULIN, days=1)
    assert usage["active_days"] == 1
    assert usage["avg_daily_units"] == 10.0
    assert usage["avg_daily_injections"] == 2.0
    assert usage["usage_per_day"] == 12.0


def test_estimate_daily_usage_isolates_basal():
    usage = estimate_daily_usage(entry_type=LogEntryType.BASAL, days=1)
    assert usage["usage_per_day"] == 0.0


def test_compute_status_when_not_configured(db_session, global_settings):
    global_settings.insulin_stock = None
    global_settings.basal_stock = None
    db_session.commit()

    status = compute_status()
    assert status["low_stock_days"] == 14
    assert status["bolus"]["configured"] is False
    assert status["basal"]["configured"] is False


def test_compute_status_with_low_bolus_stock(db_session, patient_user, global_settings):
    global_settings.insulin_stock = 20.0
    global_settings.basal_stock = 500.0
    global_settings.low_stock_days = 30
    db_session.commit()
    _log(db_session, patient_user.id, minutes_ago=5, value=5)
    _log(db_session, patient_user.id, minutes_ago=60, value=5)
    _log(
        db_session, patient_user.id, minutes_ago=5, value=20,
        entry_type=LogEntryType.BASAL,
    )
    db_session.commit()

    status = compute_status()
    bolus = status["bolus"]
    assert bolus["configured"] is True
    assert bolus["usage_per_day"] == pytest.approx(0.9)
    assert bolus["days_left"] == pytest.approx(22.2)
    assert bolus["low_stock"] is True

    basal = status["basal"]
    assert basal["configured"] is True
    assert basal["usage_per_day"] == pytest.approx(1.5)
    assert basal["days_left"] == pytest.approx(333.3)
    assert basal["low_stock"] is False


def test_compute_status_with_sufficient_stock(db_session, patient_user, global_settings):
    global_settings.insulin_stock = 1000.0
    db_session.commit()
    _log(db_session, patient_user.id, minutes_ago=5, value=5)
    _log(db_session, patient_user.id, minutes_ago=60, value=5)
    db_session.commit()

    assert compute_status()["bolus"]["low_stock"] is False


def test_evaluate_low_stock_logs_smart_alert_and_obeys_cooldown(
    db_session, patient_user, global_settings
):
    global_settings.insulin_stock = 20.0
    global_settings.basal_stock = 10.0
    global_settings.low_stock_days = 30
    db_session.commit()
    _log(db_session, patient_user.id, minutes_ago=5, value=5)
    _log(db_session, patient_user.id, minutes_ago=60, value=5)
    _log(
        db_session, patient_user.id, minutes_ago=5, value=20,
        entry_type=LogEntryType.BASAL,
    )
    db_session.commit()

    result = evaluate_low_stock()
    assert result is not None
    assert result["bolus"]["low_stock"] is True

    notes = (
        LogEntry.query
        .filter(
            LogEntry.user_id == patient_user.id,
            LogEntry.entry_type == LogEntryType.NOTE,
        )
        .order_by(LogEntry.id.desc())
        .all()
    )
    assert notes
    assert any("SmartAlert:insulin_low_stock:" in (n.notes or "") for n in notes)
    assert any("SmartAlert:basal_low_stock:" in (n.notes or "") for n in notes)

    assert evaluate_low_stock() is None


def test_evaluate_low_stock_skips_when_no_stock_configured(
    db_session, global_settings
):
    global_settings.insulin_stock = None
    global_settings.basal_stock = None
    db_session.commit()

    assert evaluate_low_stock() is None


def test_to_dict_includes_insulin_stock_fields(global_settings):
    data = global_settings.to_dict()
    assert "insulin_stock" in data
    assert "basal_stock" in data
    assert data["low_stock_days"] == 14
    assert data["insulin_low_stock_cooldown_minutes"] == 1440
    assert data["basal_low_stock_cooldown_minutes"] == 1440
