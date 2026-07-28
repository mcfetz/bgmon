"""Compression low detection — identifies false low readings from sensor compression."""

import logging
from datetime import UTC, datetime, timedelta

from bgmon_api.extensions import db
from bgmon_api.models import GlobalSettings, GlucoseReading, LogEntry, LogEntryType

logger = logging.getLogger(__name__)

STICKY_VALUES_MIN_COUNT = 3
STEEP_DROP_MGDL = 15
STEEP_DROP_MINUTES = 5
STEEP_DROP_RATE_MGDL_PER_MIN = 1.5
FLOOR_PLATEAU_MIN_COUNT = 5
FLOOR_PLATEAU_JITTER_MGDL = 2
FLOOR_PLATEAU_MAX_SGV = 70
IOB_WINDOW_MINUTES = 30
LOOKBACK_MINUTES = 15
GATING_CAP = 50
RECOVERY_JUMP_MGDL = 10
RECOVERY_JUMP_MINUTES = 3


def _has_recent_bolus(minutes: int | None = None) -> bool:
    """Check if there was a bolus insulin entry in the last N minutes."""
    window = minutes or IOB_WINDOW_MINUTES
    cutoff = datetime.now(UTC) - timedelta(minutes=window)
    count = (
        LogEntry.query
        .filter(
            LogEntry.entry_type == LogEntryType.INSULIN,
            LogEntry.unit == "U",
            LogEntry.value > 0,
            LogEntry.created_at >= cutoff,
        )
        .count()
    )
    return count > 0


def detect_compression_low() -> dict | None:
    """Analyze last LOOKBACK_MINUTES of glucose readings for compression patterns.

    Returns dict with confidence, rules, and since timestamp if compression
    low is detected (confidence >= configured threshold), otherwise None.
    """
    settings = GlobalSettings.query.first()
    if settings is None:
        settings = GlobalSettings(
            compression_low_enabled=True, compression_low_confidence_threshold=60
        )
        db.session.add(settings)
        db.session.commit()

    if not settings.compression_low_enabled:
        return None

    confidence_threshold = settings.compression_low_confidence_threshold or 60

    cutoff = datetime.now(UTC) - timedelta(minutes=LOOKBACK_MINUTES)
    readings = (
        GlucoseReading.query
        .filter(GlucoseReading.timestamp >= cutoff)
        .order_by(GlucoseReading.timestamp.asc())
        .all()
    )

    if len(readings) < 3:
        return None

    confidence = 0
    triggered_rules: list[str] = []
    confidence_components: list[int] = []

    sgv_values = [r.sgv for r in readings]

    # Rule A — STICKY_VALUES: >=3 consecutive identical SGV
    if _check_sticky(sgv_values):
        confidence += 30
        triggered_rules.append("KONSTANTE_WERTE")
        confidence_components.append(30)

    # Rule B — STEEP_DROP: >STEEP_DROP_MGDL drop <= STEEP_DROP_MINUTES, no recent IOB
    if _check_steep_drop(readings):
        has_iob = _has_recent_bolus()
        if not has_iob:
            confidence += 40
            triggered_rules.append("STARKER_ABFALL")
            confidence_components.append(40)

    # Rule C — FLOOR_PLATEAU: >=5 readings within ±JITTER at low SGV
    if _check_floor_plateau(readings):
        confidence += 30
        triggered_rules.append("BODEN_PLATEAU")
        confidence_components.append(30)

    if "STARKER_ABFALL" not in triggered_rules:
        confidence = min(confidence, GATING_CAP)

    if confidence >= confidence_threshold and triggered_rules:
        first_triggered = readings[0].timestamp if readings else datetime.now(UTC)
        return {
            "confidence": confidence,
            "confidence_components": confidence_components,
            "rules": triggered_rules,
            "since": first_triggered.isoformat() if first_triggered else None,
        }

    return None


def _check_sticky(sgv_values: list[int]) -> bool:
    """Rule A: >=3 consecutive readings with identical sgv."""
    if len(sgv_values) < STICKY_VALUES_MIN_COUNT:
        return False
    max_run = 1
    current_run = 1
    for i in range(1, len(sgv_values)):
        if sgv_values[i] == sgv_values[i - 1]:
            current_run += 1
            if current_run > max_run:
                max_run = current_run
        else:
            current_run = 1
    return max_run >= STICKY_VALUES_MIN_COUNT


def _check_steep_drop(readings: list[GlucoseReading]) -> bool:
    """Rule B: >STEEP_DROP_MGDL drop within STEEP_DROP_MINUTES at >=STEEP_DROP_RATE."""
    if len(readings) < 2:
        return False
    window_end = readings[-1].timestamp
    window_start = window_end - timedelta(minutes=STEEP_DROP_MINUTES)
    window_readings = [r for r in readings if r.timestamp >= window_start]
    window_readings.sort(key=lambda r: r.timestamp)
    if len(window_readings) < 2:
        return False
    first = window_readings[0]
    last = window_readings[-1]
    drop = first.sgv - last.sgv
    if drop <= STEEP_DROP_MGDL:
        return False
    delta_minutes = (last.timestamp - first.timestamp).total_seconds() / 60
    if delta_minutes <= 0:
        return False
    rate = drop / delta_minutes
    return rate >= STEEP_DROP_RATE_MGDL_PER_MIN


def _check_floor_plateau(readings: list[GlucoseReading]) -> bool:
    """Rule C: >=FLOOR_PLATEAU_MIN_COUNT readings within ±JITTER at low SGV."""
    if len(readings) < FLOOR_PLATEAU_MIN_COUNT:
        return False
    max_run = 1
    current_run = 1
    for i in range(1, len(readings)):
        prev = readings[i - 1]
        curr = readings[i]
        if (
            abs(curr.sgv - prev.sgv) <= FLOOR_PLATEAU_JITTER_MGDL
            and curr.sgv < FLOOR_PLATEAU_MAX_SGV
        ):
            current_run += 1
            if current_run > max_run:
                max_run = current_run
        else:
            current_run = 1
    return max_run >= FLOOR_PLATEAU_MIN_COUNT


def check_recovery_jump() -> dict | None:
    """Post-hoc validation: detect a recovery jump after a plateau.

    If within RECOVERY_JUMP_MINUTES after the end of a compression low
    detection, there is an SGV rise of ≥RECOVERY_JUMP_MGDL AND no carb
    entry logged, the compression low is confirmed.

    Returns dict with rise info for logging, or None.
    """
    settings = GlobalSettings.query.first()
    if not settings or not settings.compression_low_enabled:
        return None

    cutoff = datetime.now(UTC) - timedelta(minutes=LOOKBACK_MINUTES + 10)
    readings = (
        GlucoseReading.query
        .filter(GlucoseReading.timestamp >= cutoff)
        .order_by(GlucoseReading.timestamp.asc())
        .all()
    )
    if len(readings) < 3:
        return None

    min_sgv = min(r.sgv for r in readings)
    last_sgv = readings[-1].sgv
    rise = last_sgv - min_sgv
    if rise < RECOVERY_JUMP_MGDL:
        return None

    min_idx = max(i for i, r in enumerate(readings) if r.sgv == min_sgv)
    plateau_end = readings[min_idx].timestamp
    rise_duration = (readings[-1].timestamp - plateau_end).total_seconds() / 60
    if rise_duration > RECOVERY_JUMP_MINUTES:
        return None

    if _has_recent_bolus(minutes=IOB_WINDOW_MINUTES):
        return None

    has_carbs = (
        LogEntry.query
        .filter(
            LogEntry.entry_type == LogEntryType.CARBS,
            LogEntry.created_at >= plateau_end,
            LogEntry.created_at <= readings[-1].timestamp,
        )
        .count()
    ) > 0
    if has_carbs:
        return None

    return {
        "rise_mgdl": rise,
        "from_sgv": min_sgv,
        "to_sgv": last_sgv,
        "duration_min": round(rise_duration, 1),
        "plateau_ended_at": plateau_end.isoformat(),
    }
