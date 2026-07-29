"""Regression tests for smart-alert cooldowns and overdose detection."""

from datetime import UTC, datetime, timedelta

from bgmon_api.models import GlobalSettings, GlucoseReading, LogEntry, LogEntryType
from bgmon_api.services.smart_alerts import (
    _detect_combined_overdose,
    _detect_hypo_rebound,
    _settings,
    _was_alerted,
)


def _configure(db_session, **overrides) -> GlobalSettings:
    settings = GlobalSettings(
        insulin_action_hours=4.0,
        correction_factor=50.0,
        **overrides,
    )
    db_session.add(settings)
    db_session.commit()
    return settings


def _reading(db_session, minutes_ago: float, sgv: int) -> None:
    db_session.add(
        GlucoseReading(
            timestamp=datetime.now(UTC) - timedelta(minutes=minutes_ago),
            sgv=sgv,
            trend=4,
            direction="Flat",
            source="test",
        )
    )


def _log(
    db_session,
    user_id: int,
    entry_type: LogEntryType,
    minutes_ago: float,
    value: float,
    notes: str | None = None,
    unit: str = "U",
) -> None:
    db_session.add(
        LogEntry(
            user_id=user_id,
            entry_type=entry_type,
            value=value,
            unit=unit,
            notes=notes,
            created_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        )
    )


def test_alert_cooldown_is_configured_per_alert_type(db_session, patient_user):
    settings = _configure(
        db_session,
        hypo_rebound_cooldown_minutes=120,
        postprandial_spike_cooldown_minutes=15,
    )
    _log(
        db_session,
        patient_user.id,
        LogEntryType.NOTE,
        minutes_ago=60,
        value=0,
        unit="",
        notes="SmartAlert:hypo_rebound: Gegenregulation",
    )
    db_session.commit()

    assert _was_alerted("hypo_rebound", settings) is True
    assert _was_alerted("postprandial_spike", settings) is False


def test_hypo_rebound_is_suppressed_when_carbs_were_given(db_session, patient_user):
    _configure(db_session, rebound_require_no_carbs=True)
    for minutes_ago, sgv in ((10, 65), (9, 60), (8, 60), (7, 60), (6, 100), (5, 145)):
        _reading(db_session, minutes_ago, sgv)
    _log(
        db_session,
        patient_user.id,
        LogEntryType.CARBS,
        minutes_ago=8.5,
        value=2,
        unit="g",
    )
    db_session.commit()

    assert _detect_hypo_rebound(_settings()) is None


def test_hypo_rebound_without_carbs_is_detected(db_session, patient_user):
    _configure(db_session, rebound_require_no_carbs=True)
    assert patient_user.id is not None
    for minutes_ago, sgv in ((10, 65), (9, 60), (8, 60), (7, 60), (6, 100), (5, 145)):
        _reading(db_session, minutes_ago, sgv)
    db_session.commit()

    result = _detect_hypo_rebound(_settings())
    assert result is not None
    assert result["id"] == "hypo_rebound"


def _seed_combined_meal(
    db_session, patient_id: int, *, crash: bool, meal_minutes_ago: float = 180
) -> None:
    _log(db_session, patient_id, LogEntryType.CARBS, meal_minutes_ago, 8, unit="g")
    _log(
        db_session,
        patient_id,
        LogEntryType.INSULIN,
        meal_minutes_ago,
        10.5,
        notes="Mahlzeiten-Bolus",
    )
    _log(
        db_session,
        patient_id,
        LogEntryType.INSULIN,
        meal_minutes_ago - 1,
        1,
        notes="Korrektur: BG 144",
    )
    if crash:
        _reading(db_session, 30, 120)
        _reading(db_session, 1, 56)
    else:
        _reading(db_session, 4, 150)
        _reading(db_session, 1, 140)
    db_session.commit()


def test_combined_overdose_detects_delayed_crash(db_session, patient_user):
    _configure(db_session)
    _seed_combined_meal(db_session, patient_user.id, crash=True)

    result = _detect_combined_overdose(_settings())
    assert result is not None
    assert result["id"] == "combined_overdose"
    assert "56" in result["title"]


def test_combined_overdose_prewarns_with_high_iob_and_falling_trend(
    db_session, patient_user
):
    _configure(db_session)
    _seed_combined_meal(db_session, patient_user.id, crash=False, meal_minutes_ago=130)
    db_session.commit()

    result = _detect_combined_overdose(_settings())
    assert result is not None
    assert result["id"] == "combined_overdose"
    assert "IOB-Warnung" in result["title"]


def test_combined_overdose_ignores_later_bolus(db_session, patient_user):
    _configure(db_session)
    _seed_combined_meal(db_session, patient_user.id, crash=True)
    _log(db_session, patient_user.id, LogEntryType.INSULIN, 60, 2, notes="Mahlzeiten-Bolus")
    db_session.commit()

    assert _detect_combined_overdose(_settings()) is None
