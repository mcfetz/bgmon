"""Smart alerts — pattern detection and actionable recommendations."""

import logging
from datetime import UTC, datetime, timedelta

from bgmon_api.extensions import db
from bgmon_api.models import (
    GlobalSettings,
    GlucoseReading,
    LogEntry,
    LogEntryType,
    User,
    UserRole,
)

logger = logging.getLogger(__name__)

ALERT_DEDUP_MINUTES = 30
ALERTS = [
    "postprandial_spike",
    "hypo_rebound",
    "insulin_stacking",
    "dawn_phenomenon",
    "bouncing",
]


def _settings() -> GlobalSettings:
    s = GlobalSettings.query.first()
    if s is None:
        s = GlobalSettings()
        db.session.add(s)
        db.session.commit()
    return s


def _get_patient_id() -> int | None:
    patient = User.query.filter_by(role=UserRole.PATIENT).first()
    return patient.id if patient else None


def _was_alerted(alert_id: str, window_minutes: int | None = None) -> bool:
    """Check if this alert was already logged in the recent window."""
    patient_id = _get_patient_id()
    if not patient_id:
        return True
    window = window_minutes or ALERT_DEDUP_MINUTES
    cutoff = datetime.now(UTC) - timedelta(minutes=window)
    count = (
        LogEntry.query
        .filter(
            LogEntry.user_id == patient_id,
            LogEntry.entry_type == LogEntryType.NOTE,
            LogEntry.notes.like(f"%SmartAlert:{alert_id}:%"),
            LogEntry.created_at >= cutoff,
        )
        .count()
    )
    return count > 0


def _log_alert(alert_id: str, title: str, recommendation: str, details: str = "") -> None:
    """Log a smart alert as a NOTE in the patient's logbook."""
    patient_id = _get_patient_id()
    if not patient_id:
        return
    note = f"SmartAlert:{alert_id}: {title}. Empfehlung: {recommendation}"
    if details:
        note += f" ({details})"
    entry = LogEntry(
        user_id=patient_id,
        entry_type=LogEntryType.NOTE,
        value=0,
        unit="",
        notes=note,
    )
    db.session.add(entry)
    db.session.commit()
    logger.info("Smart alert logged: %s", alert_id)


def detect_all() -> list[dict]:
    """Run all detectors and return list of active alerts."""
    s = _settings()
    results: list[dict] = []

    spike = _detect_postprandial_spike(s)
    if spike:
        results.append(spike)

    rebound = _detect_hypo_rebound(s)
    if rebound:
        results.append(rebound)

    stacking = _detect_insulin_stacking(s)
    if stacking:
        results.append(stacking)

    dawn = _detect_dawn_phenomenon(s)
    if dawn:
        results.append(dawn)

    bounce = _detect_bouncing(s)
    if bounce:
        results.append(bounce)

    return results


# ── 1. Postprandial Spike ──────────────────────────────────────────────


def _detect_postprandial_spike(s: GlobalSettings) -> dict | None:
    if _was_alerted("postprandial_spike"):
        return None

    patient_id = _get_patient_id()
    if not patient_id:
        return None

    # Find last meal: CARBS + INSULIN entries within 5 minutes of each other
    cutoff = datetime.now(UTC) - timedelta(hours=4)
    recent_logs = (
        LogEntry.query
        .filter(
            LogEntry.user_id == patient_id,
            LogEntry.created_at >= cutoff,
            LogEntry.entry_type.in_([LogEntryType.CARBS, LogEntryType.INSULIN]),
        )
        .order_by(LogEntry.created_at.desc())
        .all()
    )

    # Find paired meals: a CARBS entry with INSULIN within 5 minutes
    last_meal_ts = None
    for log in recent_logs:
        if log.entry_type == LogEntryType.CARBS:
            for other in recent_logs:
                if other.entry_type == LogEntryType.INSULIN and abs(
                    (log.created_at - other.created_at).total_seconds()
                ) <= 300:
                    last_meal_ts = max(log.created_at, other.created_at)
                    break
        if last_meal_ts:
            break

    if not last_meal_ts:
        return None

    # Get 3 readings before meal for baseline
    pre_readings = (
        GlucoseReading.query
        .filter(
            GlucoseReading.timestamp >= last_meal_ts - timedelta(minutes=15),
            GlucoseReading.timestamp <= last_meal_ts,
        )
        .order_by(GlucoseReading.timestamp.desc())
        .limit(3)
        .all()
    )
    if len(pre_readings) < 2:
        return None
    start_bg = sum(r.sgv for r in pre_readings) // len(pre_readings)

    # Get peak within 90 min after meal
    post_readings = (
        GlucoseReading.query
        .filter(
            GlucoseReading.timestamp >= last_meal_ts,
            GlucoseReading.timestamp <= last_meal_ts + timedelta(minutes=90),
        )
        .order_by(GlucoseReading.timestamp.asc())
        .all()
    )
    if len(post_readings) < 3:
        return None
    peak_bg = max(r.sgv for r in post_readings)

    rise = peak_bg - start_bg
    if rise <= s.spike_threshold_mgdl:
        return None

    _log_alert(
        "postprandial_spike",
        f"Starker Blutzucker-Anstieg nach dem Essen (+{rise} mg/dL)",
        "Spritz 10–15 Minuten vor dem Essen, "
        "damit das Insulin gleichzeitig mit den Kohlenhydraten wirkt.",
        f"von {start_bg} auf {peak_bg}",
    )
    return {
        "id": "postprandial_spike",
        "icon": "🚀",
        "title": f"Starker Anstieg nach dem Essen (+{rise} mg/dL)",
        "recommendation": "Spritz 10–15 Minuten vor dem Essen.",
    }


# ── 2. Hypo Rebound ────────────────────────────────────────────────────


def _detect_hypo_rebound(s: GlobalSettings) -> dict | None:
    if _was_alerted("hypo_rebound"):
        return None

    patient_id = _get_patient_id()
    if not patient_id:
        return None

    window = datetime.now(UTC) - timedelta(hours=4)
    readings = (
        GlucoseReading.query
        .filter(GlucoseReading.timestamp >= window)
        .order_by(GlucoseReading.timestamp.asc())
        .all()
    )
    if len(readings) < 6:
        return None

    # Find hypo phase: >=3 consecutive readings <70
    hypo_start = None
    hypo_min = 999
    hypo_end = None
    run = 0
    for i, r in enumerate(readings):
        if r.sgv < 70:
            if run == 0:
                hypo_start = r.timestamp
            run += 1
            hypo_min = min(hypo_min, r.sgv)
            if run >= 3 and hypo_end is None and i == len(readings) - 1:
                hypo_end = r.timestamp
        else:
            if run >= 3 and hypo_end is None:
                hypo_end = readings[i - 1].timestamp
            run = 0
            if hypo_start and not hypo_end:
                hypo_start = None
                hypo_min = 999

    if not hypo_start or not hypo_end:
        return None

    # Find peak within rebound window after hypo end
    rebound_end = hypo_end + timedelta(minutes=s.rebound_window_minutes)
    post_readings = [
        r for r in readings
        if r.timestamp >= hypo_end and r.timestamp <= rebound_end
    ]
    if len(post_readings) < 3:
        return None
    peak_bg = max(r.sgv for r in post_readings)
    rise = peak_bg - hypo_min
    if rise <= s.rebound_rise_threshold_mgdl:
        return None

    # Check no carbs during the rebound
    has_carbs = (
        LogEntry.query
        .filter(
            LogEntry.user_id == patient_id,
            LogEntry.entry_type == LogEntryType.CARBS,
            LogEntry.created_at >= hypo_end,
            LogEntry.created_at <= rebound_end,
        )
        .count()
    ) > 0
    if has_carbs:
        return None

    _log_alert(
        "hypo_rebound",
        f"Gegenregulation nach Unterzuckerung (+{rise} mg/dL)",
        "Kein Korrektur-Insulin spritzen! "
        "Das ist die natürliche Reaktion des Körpers. "
        "In 1–2 Stunden normalisiert sich das.",
        f"von {hypo_min} auf {peak_bg}",
    )
    return {
        "id": "hypo_rebound",
        "icon": "🔄",
        "title": f"Gegenregulation nach Hypo (+{rise} mg/dL)",
        "recommendation": "Kein Korrektur-Insulin spritzen! In 1–2 Stunden normalisiert sich das.",
    }


# ── 3. Insulin Stacking ────────────────────────────────────────────────


def _detect_insulin_stacking(s: GlobalSettings) -> dict | None:
    if _was_alerted("insulin_stacking"):
        return None

    patient_id = _get_patient_id()
    if not patient_id:
        return None

    window = datetime.now(UTC) - timedelta(hours=s.stacking_warning_hours)
    corrections = (
        LogEntry.query
        .filter(
            LogEntry.user_id == patient_id,
            LogEntry.entry_type == LogEntryType.INSULIN,
            LogEntry.notes.like("%Korrektur%"),
            LogEntry.created_at >= window,
        )
        .order_by(LogEntry.created_at.asc())
        .all()
    )
    if len(corrections) < 2:
        return None

    first = corrections[0]
    last = corrections[-1]
    minutes_between = (last.created_at - first.created_at).total_seconds() / 60
    if minutes_between > s.stacking_warning_hours * 60:
        return None

    total_insulin = sum(c.value for c in corrections)
    remaining = s.stacking_warning_hours * 60 - minutes_between

    # Simple IOB
    now = datetime.now(UTC)
    total_hours = s.stacking_warning_hours
    iob = sum(
        c.value * max(0, 1 - (now - c.created_at).total_seconds() / (total_hours * 3600))
        for c in corrections
    )

    _log_alert(
        "insulin_stacking",
        f"Mehrere Korrektur-Gaben in {int(minutes_between)} Min",
        f"Warte {int(remaining)} Min. IOB: {iob:.1f} IE.",
        f"{len(corrections)} Korrekturen, {total_insulin:.1f} IE gesamt",
    )
    return {
        "id": "insulin_stacking",
        "icon": "💉",
        "title": f"Insulin-Stacking ({len(corrections)} Korrekturen in {int(minutes_between)} Min)",
        "recommendation": f"Warte {int(remaining)} Min. IOB: {iob:.1f} IE.",
    }


# ── 4. Dawn Phenomenon ─────────────────────────────────────────────────


def _detect_dawn_phenomenon(s: GlobalSettings) -> dict | None:
    if _was_alerted("dawn_phenomenon"):
        return None

    now = datetime.now(UTC)
    today_start = now.replace(hour=s.dawn_start_hour_utc, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=s.dawn_end_hour_utc, minute=0, second=0, microsecond=0)

    if not (today_start <= now <= today_end):
        return None

    patient_id = _get_patient_id()
    if not patient_id:
        return None

    readings = (
        GlucoseReading.query
        .filter(
            GlucoseReading.timestamp >= today_start,
            GlucoseReading.timestamp <= today_end,
        )
        .order_by(GlucoseReading.timestamp.asc())
        .all()
    )
    if len(readings) < 3:
        return None

    start_sgv = readings[0].sgv
    end_sgv = readings[-1].sgv
    rise = end_sgv - start_sgv
    if rise <= s.dawn_rise_threshold_mgdl:
        return None

    has_carbs = (
        LogEntry.query
        .filter(
            LogEntry.user_id == patient_id,
            LogEntry.entry_type == LogEntryType.CARBS,
            LogEntry.created_at >= today_start,
            LogEntry.created_at <= today_end,
        )
        .count()
    ) > 0
    if has_carbs:
        return None

    _log_alert(
        "dawn_phenomenon",
        f"Dawn-Phänomen (+{rise} mg/dL)",
        "Basalrate morgens prüfen. Sprich mit dem Diabetes-Team.",
        f"von {start_sgv} auf {end_sgv}",
    )
    return {
        "id": "dawn_phenomenon",
        "icon": "🌅",
        "title": f"Dawn-Phänomen (+{rise} mg/dL)",
        "recommendation": "Basalrate morgens prüfen. Sprich mit dem Diabetes-Team.",
    }


# ── 5. Bouncing ────────────────────────────────────────────────────────


def _detect_bouncing(s: GlobalSettings) -> dict | None:
    if _was_alerted("bouncing"):
        return None

    window = datetime.now(UTC) - timedelta(hours=s.bounce_window_hours)
    readings = (
        GlucoseReading.query
        .filter(GlucoseReading.timestamp >= window)
        .order_by(GlucoseReading.timestamp.asc())
        .all()
    )
    if len(readings) < 10:
        return None

    # Find pattern: hypo → hyper → hypo (in sequence)
    phases: list[tuple[str, int]] = []
    current_phase = None
    phase_start = None

    for r in readings:
        if r.sgv < s.bounce_hypo_threshold:
            new_phase = "hypo"
        elif r.sgv > s.bounce_hyper_threshold:
            new_phase = "hyper"
        else:
            continue

        if new_phase != current_phase:
            if current_phase is not None:
                extreme = _get_extreme(readings, current_phase, phase_start, r.timestamp)
                phases.append((current_phase, extreme))
            current_phase = new_phase
            phase_start = r.timestamp

    if current_phase is not None:
        phases.append((current_phase, 0))

    # Check for hypo → hyper → hypo pattern
    for i in range(len(phases) - 2):
        if phases[i][0] == "hypo" and phases[i + 1][0] == "hyper" and phases[i + 2][0] == "hypo":
            _log_alert(
                "bouncing",
                "Korrektur-Überkorrektur-Kreislauf! "
                "Blutzucker springt zwischen Unter- und Überzuckerung.",
                "Korrektur-Insulin reduzieren. "
                "Nach Unterzuckerung 2h warten bis zur Selbstregulation.",
                f"in {s.bounce_window_hours}h",
            )
            return {
                "id": "bouncing",
                "icon": "🎢",
                "title": "Überkorrektur-Kreislauf erkannt",
                "recommendation": "Korrektur-Insulin reduzieren. Nach Hypo 2h warten.",
            }

    return None


def _get_extreme(readings: list, phase: str, start_ts, end_ts) -> int:
    vals = [
        r.sgv for r in readings
        if start_ts and r.timestamp >= start_ts and r.timestamp <= end_ts
    ]
    if not vals:
        return 0
    return max(vals) if phase == "hyper" else min(vals)
