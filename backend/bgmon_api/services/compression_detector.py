"""Compression low detection — identifies false low readings from sensor compression."""

import logging
from datetime import UTC, datetime, timedelta

from bgmon_api.extensions import db
from bgmon_api.models import GlobalSettings, GlucoseReading, LogEntry, LogEntryType

logger = logging.getLogger(__name__)

STICKY_VALUES_MIN_COUNT = 3
STEEP_DROP_MGDL = 15
STEEP_DROP_MINUTES = 5
FLOOR_PLATEAU_MIN_COUNT = 5
FLOOR_PLATEAU_JITTER_MGDL = 2
FLOOR_PLATEAU_MAX_SGV = 80
IOB_WINDOW_MINUTES = 30
LOOKBACK_MINUTES = 15


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
    """Rule B: >STEEP_DROP_MGDL drop within STEEP_DROP_MINUTES."""
    if len(readings) < 2:
        return False
    window_end = readings[-1].timestamp
    window_start = window_end - timedelta(minutes=STEEP_DROP_MINUTES)
    window_readings = [r for r in readings if r.timestamp >= window_start]
    window_readings.sort(key=lambda r: r.timestamp)
    if len(window_readings) < 2:
        return False
    first_sgv = window_readings[0].sgv
    last_sgv = window_readings[-1].sgv
    return first_sgv - last_sgv > STEEP_DROP_MGDL


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
