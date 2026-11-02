"""Regression tests for smart-alert cooldowns and overdose detection."""

from datetime import UTC, datetime, timedelta

from bgmon_api.models import GlobalSettings, GlucoseReading, LogEntry, LogEntryType
from bgmon_api.services.smart_alerts import (
    _detect_combined_overdose,
    _detect_hypo_rebound,
    _detect_postprandial_spike,
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
    _configure(db_session, rebound_require_no_carbs=True, rebound_slope_enabled=False)
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


def test_hypo_rebound_ignores_late_onset_rise(db_session, patient_user):
    """A rise that only begins long after the hypo is a separate event."""
    _configure(db_session, rebound_require_no_carbs=True)
    assert patient_user.id is not None
    # Night hypo recovers on its own, then a late (meal-driven) excursion.
    series = (
        (200, 64), (195, 67), (190, 68), (185, 90), (180, 92), (175, 91),
        (170, 95),
        (60, 96), (55, 100), (50, 130), (45, 180), (40, 236), (35, 250),
    )
    for minutes_ago, sgv in series:
        _reading(db_session, minutes_ago, sgv)
    db_session.commit()

    assert _detect_hypo_rebound(_settings()) is None


def test_hypo_rebound_branch_a_suppressed_by_carbs_in_rebound_window(
    db_session, patient_user,
):
    """Branch A keeps its carb guard: carbs explain the rise."""
    _configure(
        db_session,
        rebound_require_no_carbs=True,
        rebound_slope_enabled=False,
    )
    assert patient_user.id is not None
    for minutes_ago, sgv in (
        (60, 64),
        (58, 65),
        (55, 66),
        (50, 90),
        (30, 110),
        (20, 190),
    ):
        _reading(db_session, minutes_ago, sgv)
    _log(db_session, patient_user.id, LogEntryType.CARBS, minutes_ago=25, value=5, unit="KE")
    db_session.commit()

    assert _detect_hypo_rebound(_settings()) is None


def test_hypo_rebound_branch_a_carb_guard_survives_a_later_dip(db_session, patient_user):
    """A later one-off dip must not reopen the episode and disarm the guard.

    Production 2026-10-06: the 07:28-07:58 hypo was correctly suppressed by
    the 07:51 carbs, but a single 68 mg/dL reading at 11:10 rewrote
    ``hypo_start`` while ``hypo_end`` stayed at 07:58. The guard then
    queried the inverted window [11:10, 09:58], found nothing and let a
    three-hour-stale alert through.
    """
    _configure(
        db_session,
        rebound_require_no_carbs=True,
        rebound_slope_enabled=False,
    )
    assert patient_user.id is not None
    for minutes_ago, sgv in (
        (60, 64),
        (58, 65),
        (55, 66),
        (50, 90),
        (30, 110),
        (20, 190),
        (5, 68),
    ):
        _reading(db_session, minutes_ago, sgv)
    _log(db_session, patient_user.id, LogEntryType.CARBS, minutes_ago=25, value=5, unit="KE")
    db_session.commit()

    assert _detect_hypo_rebound(_settings()) is None


def test_hypo_rebound_later_dip_does_not_change_reported_minimum(
    db_session, patient_user,
):
    _configure(db_session, rebound_require_no_carbs=True, rebound_slope_enabled=False)
    assert patient_user.id is not None
    for minutes_ago, sgv in (
        (60, 64),
        (58, 65),
        (55, 66),
        (50, 90),
        (30, 110),
        (20, 190),
        (5, 55),
    ):
        _reading(db_session, minutes_ago, sgv)
    db_session.commit()

    result = _detect_hypo_rebound(_settings())
    assert result is not None
    # Rise is measured from the episode minimum (64), not the later 55.
    assert result["title"] == "Gegenregulation nach Unterzuckerung (+126 mg/dL)"


def _late_rebound_series(db_session) -> None:
    """58 → 123 (T+40) → 178 (T+55): the steep part starts behind the onset window.

    Within the 40-minute onset window the rise stays at 65 mg/dL, so branch A
    cannot fire; only the 30-minute slope from T+45 on is steep enough.
    """
    series = (
        (70, 65), (68, 62), (66, 58), (64, 60),
        (60, 64), (55, 66), (50, 70), (45, 74),
        (40, 80), (35, 88), (30, 100), (25, 112),
        (20, 123), (15, 140), (10, 158), (5, 178),
    )
    for minutes_ago, sgv in series:
        _reading(db_session, minutes_ago, sgv)


def test_hypo_rebound_branch_b_fires_on_late_steep_rise(db_session, patient_user):
    """Branch B catches a rebound whose steep part starts after the onset window."""
    _configure(db_session, rebound_rise_threshold_mgdl=80)
    assert patient_user.id is not None
    _late_rebound_series(db_session)
    db_session.commit()

    result = _detect_hypo_rebound(_settings())
    assert result is not None
    assert result["id"] == "hypo_rebound"
    assert "Unterzuckerung" in result["title"]
    assert "normalisiert sich" not in result["recommendation"]
    assert "zweite Phase" in result["recommendation"]


def test_hypo_rebound_branch_b_can_be_disabled(db_session, patient_user):
    """The kill switch restores the pre-2026-11-02 behaviour."""
    _configure(db_session, rebound_rise_threshold_mgdl=80, rebound_slope_enabled=False)
    assert patient_user.id is not None
    _late_rebound_series(db_session)
    db_session.commit()

    assert _detect_hypo_rebound(_settings()) is None


def test_hypo_rebound_branch_b_alerts_with_rescue_carbs(db_session, patient_user):
    """Rescue carbs (no bolus) no longer silence the alert — they pick the text."""
    _configure(db_session)
    assert patient_user.id is not None
    _late_rebound_series(db_session)
    _log(db_session, patient_user.id, LogEntryType.CARBS, 58, 1.3, unit="KE")
    db_session.commit()

    result = _detect_hypo_rebound(_settings())
    assert result is not None
    assert "mit Kohlenhydraten" in result["title"]
    assert "Kohlenhydrate" in result["recommendation"]

    notes = [
        entry for entry in LogEntry.query.filter_by(
            user_id=patient_user.id, entry_type=LogEntryType.NOTE
        ).all()
        if "SmartAlert:hypo_rebound:" in (entry.notes or "")
    ]
    assert notes
    assert "mit Kohlenhydraten" in (notes[-1].notes or "")


def test_hypo_rebound_branch_b_ignores_meal_carbs(db_session, patient_user):
    """Carbs with a bolus ±15 min are a meal — postprandial_spike is responsible."""
    _configure(db_session)
    assert patient_user.id is not None
    _late_rebound_series(db_session)
    _log(db_session, patient_user.id, LogEntryType.CARBS, 25, 4, unit="KE")
    _log(db_session, patient_user.id, LogEntryType.INSULIN, 24, 5, notes="Mahlzeiten-Bolus")
    db_session.commit()

    assert _detect_hypo_rebound(_settings()) is None


def test_hypo_rebound_flat_curve_after_low_does_not_fire(db_session, patient_user):
    _configure(db_session)
    assert patient_user.id is not None
    for minutes_ago, sgv in (
        (70, 66), (68, 64), (66, 62), (64, 65),
        (50, 70), (45, 74), (40, 78), (35, 80), (30, 82),
        (25, 84), (20, 86), (15, 88), (10, 90), (5, 92),
    ):
        _reading(db_session, minutes_ago, sgv)
    db_session.commit()

    assert _detect_hypo_rebound(_settings()) is None


def test_hypo_rebound_cooldown_blocks_a_second_note(db_session, patient_user):
    _configure(db_session, hypo_rebound_cooldown_minutes=120)
    assert patient_user.id is not None
    _late_rebound_series(db_session)
    _log(
        db_session,
        patient_user.id,
        LogEntryType.NOTE,
        60,
        0,
        unit="",
        notes="SmartAlert:hypo_rebound: Gegenregulation nach Unterzuckerung",
    )
    db_session.commit()

    assert _detect_hypo_rebound(_settings()) is None


def test_postprandial_spike_reports_a_fresh_spike(db_session, patient_user):
    _configure(db_session, spike_threshold_mgdl=100)
    assert patient_user.id is not None
    for minutes_ago, sgv in (
        (72, 63),
        (68, 64),
        (63, 63),
        (50, 100),
        (40, 140),
        (30, 174),
        (15, 150),
    ):
        _reading(db_session, minutes_ago, sgv)
    _log(db_session, patient_user.id, LogEntryType.CARBS, minutes_ago=60, value=60, unit="g")
    _log(db_session, patient_user.id, LogEntryType.INSULIN, minutes_ago=59, value=6, unit="U")
    db_session.commit()

    result = _detect_postprandial_spike(_settings())
    assert result is not None
    assert result["id"] == "postprandial_spike"


def test_postprandial_spike_is_not_re_reported_after_the_peak_window(
    db_session, patient_user,
):
    """The same meal must not be reported again once its peak window is over.

    Production 2026-10-06: the 07:51 meal was reported at 08:39 and again at
    10:39 (cooldown expiry) with the old peak, while BG had long returned to
    90 mg/dL.
    """
    _configure(db_session, spike_threshold_mgdl=100)
    assert patient_user.id is not None
    for minutes_ago, sgv in (
        (112, 63),
        (108, 64),
        (103, 63),
        (80, 100),
        (60, 140),
        (40, 174),
        (20, 150),
    ):
        _reading(db_session, minutes_ago, sgv)
    _log(db_session, patient_user.id, LogEntryType.CARBS, minutes_ago=100, value=60, unit="g")
    _log(db_session, patient_user.id, LogEntryType.INSULIN, minutes_ago=99, value=6, unit="U")
    db_session.commit()

    assert _detect_postprandial_spike(_settings()) is None


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


def test_combined_overdose_prewarn_names_the_measured_crash_window(
    db_session, patient_user,
):
    """The pre-warning text must not promise a one-hour window.

    Measured crashes followed 2 h 38 to 2 h 53 after the alert.
    """
    _configure(db_session)
    _seed_combined_meal(db_session, patient_user.id, crash=False, meal_minutes_ago=130)
    db_session.commit()

    assert _detect_combined_overdose(_settings()) is not None

    note = (
        LogEntry.query
        .filter_by(user_id=patient_user.id, entry_type=LogEntryType.NOTE)
        .order_by(LogEntry.id.desc())
        .first()
    )
    assert note is not None
    assert "1–3 Stunden" in (note.notes or "")
    assert "nächsten Stunde " not in (note.notes or "")
