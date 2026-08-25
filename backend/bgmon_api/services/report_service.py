"""AGP report data aggregation — pure computation, no Flask imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from bgmon_api.models import GlucoseReading, LogEntry, LogEntryType
from bgmon_api.utils import compute_glucose_stats

LOCAL_TZ = ZoneInfo("Europe/Berlin")

# TIR thresholds (mg/dL) — matches FreeStyle defaults
LOW = 70
HIGH = 180
CRITICAL_LOW = 54
CRITICAL_HIGH = 250

# AGP percentile buckets: 30-minute intervals over 24h
_AGP_BUCKET_MINUTES = 30
_AGP_BUCKETS_PER_DAY = 24 * 60 // _AGP_BUCKET_MINUTES  # 48

# Meal time blocks (local hours)
_MEAL_BLOCKS = {
    "morning": (4, 10),
    "midday": (10, 16),
    "evening": (16, 22),
    "night": (22, 28),  # wraps past midnight
}


# ── Data classes ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ReportPeriod:
    """Report date range metadata."""

    start: str
    end: str
    num_days: int


@dataclass(frozen=True, slots=True)
class GlucoseStats:
    """Aggregate glucose statistics for the report period."""

    mean: float | None
    tir_percent: float | None
    tir_below: float | None
    tir_above: float | None
    gmi: float | None
    cv_percent: float | None
    std_dev: float | None
    readings: int
    min_val: float | None
    max_val: float | None
    sensor_active_percent: float | None
    time_below_54: float | None
    time_54_70: float | None
    time_70_180: float | None
    time_180_250: float | None
    time_above_250: float | None


@dataclass(frozen=True, slots=True)
class AGPPoint:
    """Single point on the AGP curve at a specific time-of-day bucket."""

    bucket_index: int
    time_label: str
    p5: float | None
    p25: float | None
    p50: float | None
    p75: float | None
    p95: float | None


@dataclass(frozen=True, slots=True)
class DailyProfile:
    """Single day glucose profile with carb/insulin totals."""

    date: str
    weekday: str
    readings: list[tuple[str, int]]  # (HH:MM, sgv)
    avg: float | None
    carbs_total: float | None
    insulin_total: float | None
    hypo_events: int


@dataclass(frozen=True, slots=True)
class DayOverview:
    """Calendar day summary for the monthly overview."""

    date: str
    weekday: str
    avg_sgv: float | None
    carbs_grams: float | None
    insulin_units: float | None
    hypo_events: int
    reading_count: int


@dataclass(frozen=True, slots=True)
class IntervalMinMax:
    """Min/max glucose in a 2-hour interval."""

    time_start: str
    time_end: str
    min_val: int | None
    max_val: int | None


@dataclass(frozen=True, slots=True)
class DayProtocol:
    """Daily protocol with 2-hour interval min/max values."""

    date: str
    weekday: str
    intervals: list[IntervalMinMax]


@dataclass(frozen=True, slots=True)
class LowGlucoseEvent:
    """A single hypoglycemic episode."""

    date: str
    time: str
    sgv: int
    duration_minutes: int


@dataclass(frozen=True, slots=True)
class ReportSnapshot:
    """Summary snapshot for the report period."""

    mean_sgv: float | None
    gmi: float | None
    tir_percent: float | None
    below_percent: float | None
    above_percent: float | None
    low_events_count: int
    low_events_avg_duration_minutes: float | None
    sensor_active_percent: float | None
    avg_scans_per_day: float | None
    carbs_daily_avg_grams: float | None
    insulin_daily_avg_units: float | None
    low_events: list[LowGlucoseEvent]


@dataclass(frozen=True, slots=True)
class MealPoint:
    """Glucose value relative to a meal event."""

    offset_label: str  # "-1h", "+1h", "+2h", "+3h"
    median_sgv: float | None
    p25: float | None
    p75: float | None


@dataclass(frozen=True, slots=True)
class MealBlock:
    """Meal-time glucose profile for a time block (morning/midday/evening/night)."""

    name: str  # "morning", "midday", "evening", "night"
    hours_label: str
    points: list[MealPoint]


@dataclass(frozen=True, slots=True)
class DailyPatternPoint:
    """AGP-like pattern point with carb/insulin distribution."""

    time_label: str
    p5: float | None
    p25: float | None
    p50: float | None
    p75: float | None
    p95: float | None
    carbs_avg: float | None
    insulin_avg: float | None


@dataclass(frozen=True, slots=True)
class WeeklyDay:
    """Single day for the weekly overview with sparkline data."""

    date: str
    weekday: str
    glucose_points: list[tuple[str, int]]  # (HH:MM, sgv) for sparkline
    avg_sgv: float | None
    carbs_grams: float | None
    insulin_units: float | None
    hypo_events: int


@dataclass(slots=True)
class ReportData:
    """Complete AGP report data structure."""

    period: ReportPeriod
    glucose_stats: GlucoseStats
    agp_curve: list[AGPPoint]
    daily_profiles: list[DailyProfile]
    monthly_overview: list[DayOverview]
    daily_protocols: list[DayProtocol]
    snapshot: ReportSnapshot
    meal_profile: list[MealBlock]
    daily_pattern: list[DailyPatternPoint]
    weekly_overview: list[WeeklyDay]


# ── Timezone helpers ────────────────────────────────────────────────────


def _to_local(ts: datetime) -> datetime:
    """Convert UTC timestamp to Europe/Berlin."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(LOCAL_TZ)


def _time_of_day_minutes(ts: datetime) -> int:
    """Minutes since midnight in local time."""
    lt = _to_local(ts)
    return lt.hour * 60 + lt.minute


def _date_key(ts: datetime) -> str:
    """YYYY-MM-DD in local time."""
    return _to_local(ts).strftime("%Y-%m-%d")


def _weekday_de(ts: datetime) -> str:
    """German weekday name."""
    days = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    return days[_to_local(ts).weekday()]


def _time_label(minutes: int) -> str:
    """HH:MM from minutes since midnight."""
    h, m = divmod(minutes, 60)
    return f"{h:02d}:{m:02d}"


def _bucket_index(minutes: int) -> int:
    """Map minutes-since-midnight to AGP bucket index."""
    return min(minutes // _AGP_BUCKET_MINUTES, _AGP_BUCKETS_PER_DAY - 1)


# ── Core aggregation ───────────────────────────────────────────────────


def _collect_local(
    readings: list[GlucoseReading],
    entries: list[LogEntry],
) -> tuple[
    list[GlucoseReading],
    list[LogEntry],
    list[int],
    dict[str, list[GlucoseReading]],
    dict[str, list[LogEntry]],
]:
    """Organize readings/entries by local date and collect all sgv values."""
    readings_by_date: dict[str, list[GlucoseReading]] = {}
    entries_by_date: dict[str, list[LogEntry]] = {}
    all_sgv: list[int] = []

    for r in readings:
        if r.sgv is None:
            continue
        dk = _date_key(r.timestamp)
        readings_by_date.setdefault(dk, []).append(r)
        all_sgv.append(r.sgv)

    for e in entries:
        dk = _date_key(e.created_at)
        entries_by_date.setdefault(dk, []).append(e)

    return readings, entries, all_sgv, readings_by_date, entries_by_date


def _compute_sensor_stats(
    readings: list[GlucoseReading], total_days: int
) -> float:
    """Estimate sensor active % from reading density."""
    if not readings or total_days <= 0:
        return 0.0
    expected = total_days * 24 * 60  # one reading per minute theoretical
    return round(min(100.0, len(readings) / max(expected, 1) * 100), 1)


def _compute_time_in_bands(
    all_sgv: list[int],
) -> tuple[float, float, float, float, float]:
    """Compute % in each glucose band."""
    n = len(all_sgv)
    if n == 0:
        return (0.0, 0.0, 0.0, 0.0, 0.0)
    below_54 = sum(1 for v in all_sgv if v < CRITICAL_LOW) / n * 100
    b54_70 = sum(1 for v in all_sgv if CRITICAL_LOW <= v < LOW) / n * 100
    b70_180 = sum(1 for v in all_sgv if LOW <= v <= HIGH) / n * 100
    b180_250 = sum(1 for v in all_sgv if HIGH < v <= CRITICAL_HIGH) / n * 100
    above_250 = sum(1 for v in all_sgv if v > CRITICAL_HIGH) / n * 100
    return (
        round(below_54, 1),
        round(b54_70, 1),
        round(b70_180, 1),
        round(b180_250, 1),
        round(above_250, 1),
    )


def _compute_cv(all_sgv: list[int]) -> float | None:
    """Coefficient of variation (%)."""
    if len(all_sgv) < 2:
        return None
    mean = sum(all_sgv) / len(all_sgv)
    if mean == 0:
        return None
    variance = sum((v - mean) ** 2 for v in all_sgv) / len(all_sgv)
    return round((variance**0.5) / mean * 100, 1)


def _compute_glucose_stats(all_sgv: list[int]) -> GlucoseStats:
    base = compute_glucose_stats([float(v) for v in all_sgv], LOW, HIGH)
    b54, b70, b70180, b180250, above250 = _compute_time_in_bands(all_sgv)
    return GlucoseStats(
        mean=base["mean"],
        tir_percent=base["tir_percent"],
        tir_below=base["tir_below"],
        tir_above=base["tir_above"],
        gmi=base["gmi"],
        cv_percent=_compute_cv(all_sgv),
        std_dev=base["std_dev"],
        readings=base["readings"],
        min_val=base["min"],
        max_val=base["max"],
        sensor_active_percent=None,  # computed later with actual readings
        time_below_54=b54,
        time_54_70=b70,
        time_70_180=b70180,
        time_180_250=b180250,
        time_above_250=above250,
    )


# ── AGP curve ──────────────────────────────────────────────────────────


def _compute_agp_curve(
    readings: list[GlucoseReading],
) -> list[AGPPoint]:
    """Compute 5./25./50./75./95. percentiles over 24h in30-min buckets."""
    import numpy as np

    buckets: list[list[int]] = [[] for _ in range(_AGP_BUCKETS_PER_DAY)]
    for r in readings:
        if r.sgv is None:
            continue
        bi = _bucket_index(_time_of_day_minutes(r.timestamp))
        buckets[bi].append(r.sgv)

    points: list[AGPPoint] = []
    for i in range(_AGP_BUCKETS_PER_DAY):
        vals = buckets[i]
        if not vals:
            points.append(
                AGPPoint(
                    bucket_index=i,
                    time_label=_time_label(i * _AGP_BUCKET_MINUTES),
                    p5=None,
                    p25=None,
                    p50=None,
                    p75=None,
                    p95=None,
                )
            )
            continue
        arr = np.array(vals, dtype=float)
        p5, p25, p50, p75, p95 = np.percentile(arr, [5, 25, 50, 75, 95])
        points.append(
            AGPPoint(
                bucket_index=i,
                time_label=_time_label(i * _AGP_BUCKET_MINUTES),
                p5=round(float(p5), 1),
                p25=round(float(p25), 1),
                p50=round(float(p50), 1),
                p75=round(float(p75), 1),
                p95=round(float(p95), 1),
            )
        )
    return points


# ── Daily profiles ──────────────────────────────────────────────────────


def _compute_daily_profiles(
    readings_by_date: dict[str, list[GlucoseReading]],
    entries_by_date: dict[str, list[LogEntry]],
) -> list[DailyProfile]:
    profiles: list[DailyProfile] = []
    for dk in sorted(readings_by_date):
        day_readings = sorted(readings_by_date[dk], key=lambda r: r.timestamp)
        sgvs = [r.sgv for r in day_readings if r.sgv is not None]
        day_entries = entries_by_date.get(dk, [])
        carbs = sum(e.value for e in day_entries if e.entry_type == LogEntryType.CARBS)
        insulin = sum(e.value for e in day_entries if e.entry_type == LogEntryType.INSULIN)

        first_ts = day_readings[0].timestamp if day_readings else datetime.now(UTC)
        hypo = sum(1 for v in sgvs if v < LOW)

        points = [
            (_to_local(r.timestamp).strftime("%H:%M"), r.sgv)
            for r in day_readings
            if r.sgv is not None
        ]
        profiles.append(
            DailyProfile(
                date=dk,
                weekday=_weekday_de(first_ts),
                readings=points,
                avg=round(sum(sgvs) / len(sgvs), 1) if sgvs else None,
                carbs_total=carbs if carbs > 0 else None,
                insulin_total=insulin if insulin > 0 else None,
                hypo_events=hypo,
            )
        )
    return profiles


# ── Monthly overview (calendar) ────────────────────────────────────────


def _compute_monthly_overview(
    readings_by_date: dict[str, list[GlucoseReading]],
    entries_by_date: dict[str, list[LogEntry]],
) -> list[DayOverview]:
    overview: list[DayOverview] = []
    for dk in sorted(readings_by_date):
        sgvs = [r.sgv for r in readings_by_date[dk] if r.sgv is not None]
        day_entries = entries_by_date.get(dk, [])
        carbs = sum(e.value for e in day_entries if e.entry_type == LogEntryType.CARBS)
        insulin = sum(e.value for e in day_entries if e.entry_type == LogEntryType.INSULIN)
        hypo = sum(1 for v in sgvs if v < LOW)
        ts = readings_by_date[dk][0].timestamp
        overview.append(
            DayOverview(
                date=dk,
                weekday=_weekday_de(ts),
                avg_sgv=round(sum(sgvs) / len(sgvs), 1) if sgvs else None,
                carbs_grams=carbs if carbs > 0 else None,
                insulin_units=insulin if insulin > 0 else None,
                hypo_events=hypo,
                reading_count=len(sgvs),
            )
        )
    return overview


# ── Daily protocol (2h intervals) ──────────────────────────────────────


def _compute_daily_protocols(
    readings_by_date: dict[str, list[GlucoseReading]],
) -> list[DayProtocol]:
    """Per-day, per-2h-interval min/max."""
    protocols: list[DayProtocol] = []
    for dk in sorted(readings_by_date):
        day_readings = readings_by_date[dk]
        ts_first = day_readings[0].timestamp if day_readings else datetime.now(UTC)
        intervals: list[IntervalMinMax] = []

        for h in range(0, 24, 2):
            start_min = h * 60
            end_min = (h + 2) * 60
            bucket: list[int] = []
            for r in day_readings:
                if r.sgv is None:
                    continue
                tod = _time_of_day_minutes(r.timestamp)
                if start_min <= tod < end_min:
                    bucket.append(r.sgv)
            intervals.append(
                IntervalMinMax(
                    time_start=_time_label(start_min),
                    time_end=_time_label(end_min % (24 * 60)),
                    min_val=min(bucket) if bucket else None,
                    max_val=max(bucket) if bucket else None,
                )
            )
        protocols.append(
            DayProtocol(
                date=dk,
                weekday=_weekday_de(ts_first),
                intervals=intervals,
            )
        )
    return protocols


# ── Snapshot ────────────────────────────────────────────────────────────


def _compute_low_events(
    readings: list[GlucoseReading],
) -> tuple[list[LowGlucoseEvent], int, float | None]:
    """Identify low glucose episodes (consecutive readings <70)."""
    sorted_r = sorted(
        [r for r in readings if r.sgv is not None], key=lambda r: r.timestamp
    )
    events: list[LowGlucoseEvent] = []
    in_low = False
    low_start: datetime | None = None
    low_min_sgv = 999

    for r in sorted_r:
        if r.sgv is not None and r.sgv < LOW:
            if not in_low:
                in_low = True
                low_start = r.timestamp
                low_min_sgv = r.sgv
            else:
                low_min_sgv = min(low_min_sgv, r.sgv)
        else:
            if in_low and low_start is not None:
                duration = (r.timestamp - low_start).total_seconds() / 60
                lt = _to_local(low_start)
                events.append(
                    LowGlucoseEvent(
                        date=lt.strftime("%Y-%m-%d"),
                        time=lt.strftime("%H:%M"),
                        sgv=low_min_sgv,
                        duration_minutes=max(1, int(duration)),
                    )
                )
                in_low = False

    if in_low and low_start is not None:
        last_ts = sorted_r[-1].timestamp if sorted_r else datetime.now(UTC)
        duration = (last_ts - low_start).total_seconds() / 60
        lt = _to_local(low_start)
        events.append(
            LowGlucoseEvent(
                date=lt.strftime("%Y-%m-%d"),
                time=lt.strftime("%H:%M"),
                sgv=low_min_sgv,
                duration_minutes=max(1, int(duration)),
            )
        )

    avg_duration = (
        round(sum(e.duration_minutes for e in events) / len(events), 0)
        if events
        else None
    )
    return events, len(events), avg_duration


def _compute_snapshot(
    readings: list[GlucoseReading],
    entries: list[LogEntry],
    period_days: int,
    glucose_stats: GlucoseStats,
) -> ReportSnapshot:
    low_events, low_count, low_avg_dur = _compute_low_events(readings)

    total_carbs = sum(
        e.value for e in entries if e.entry_type == LogEntryType.CARBS
    )
    total_insulin = sum(
        e.value for e in entries if e.entry_type == LogEntryType.INSULIN
    )
    days_with_carbs = len(
        {
            _date_key(e.created_at)
            for e in entries
            if e.entry_type == LogEntryType.CARBS
        }
    )
    days_with_insulin = len(
        {
            _date_key(e.created_at)
            for e in entries
            if e.entry_type == LogEntryType.INSULIN
        }
    )

    return ReportSnapshot(
        mean_sgv=glucose_stats.mean,
        gmi=glucose_stats.gmi,
        tir_percent=glucose_stats.tir_percent,
        below_percent=glucose_stats.tir_below,
        above_percent=glucose_stats.tir_above,
        low_events_count=low_count,
        low_events_avg_duration_minutes=low_avg_dur,
        sensor_active_percent=glucose_stats.sensor_active_percent,
        avg_scans_per_day=(
            round(len(readings) / period_days, 1) if period_days > 0 else None
        ),
        carbs_daily_avg_grams=(
            round(total_carbs / days_with_carbs, 1) if days_with_carbs > 0 else None
        ),
        insulin_daily_avg_units=(
            round(total_insulin / days_with_insulin, 1)
            if days_with_insulin > 0
            else None
        ),
        low_events=low_events,
    )


# ── Meal profile ────────────────────────────────────────────────────────


def _compute_meal_profile(
    readings: list[GlucoseReading],
    entries: list[LogEntry],
) -> list[MealBlock]:
    """For each meal block, compute glucose pre/post meal medians."""
    import numpy as np

    sorted_readings = sorted(readings, key=lambda r: r.timestamp)
    carb_entries = [
        e for e in entries if e.entry_type == LogEntryType.CARBS and e.value > 0
    ]
    if not carb_entries or not sorted_readings:
        return []

    reading_timestamps = [r.timestamp for r in sorted_readings]
    reading_sgvs = np.array([r.sgv for r in sorted_readings])

    blocks: list[MealBlock] = []
    for name, (h_start, h_end) in _MEAL_BLOCKS.items():
        hours_label = f"{h_start:02d}:00 - {h_end % 24:02d}:00"

        # Filter carb entries in this time block
        block_entries = []
        for e in carb_entries:
            lt = _to_local(e.created_at)
            e_hour = lt.hour + lt.minute / 60.0
            if h_start < 24:
                if h_start <= e_hour < h_end:
                    block_entries.append(e)
            else:
                # wraps past midnight
                if e_hour >= h_start or e_hour < h_end % 24:
                    block_entries.append(e)

        if not block_entries:
            blocks.append(
                MealBlock(
                    name=name,
                    hours_label=hours_label,
                    points=[],
                )
            )
            continue

        # For each carb entry, find glucose at -1h, +1h, +2h, +3h
        offsets = [
            ("-1h", -3600),
            ("+1h", 3600),
            ("+2h", 7200),
            ("+3h", 10800),
        ]
        points: list[MealPoint] = []
        for offset_label, offset_seconds in offsets:
            values: list[float] = []
            for e in carb_entries:
                target_ts = e.created_at + timedelta(seconds=offset_seconds)
                # Find nearest reading
                idx = _find_nearest_idx(reading_timestamps, target_ts)
                if idx is not None:
                    diff = abs((reading_timestamps[idx] - target_ts).total_seconds())
                    if diff <= 900:  # within15 min tolerance
                        values.append(float(reading_sgvs[idx]))
            if values:
                arr = np.array(values)
                p25, p50, p75 = np.percentile(arr, [25, 50, 75])
                points.append(
                    MealPoint(
                        offset_label=offset_label,
                        median_sgv=round(float(p50), 1),
                        p25=round(float(p25), 1),
                        p75=round(float(p75), 1),
                    )
                )
            else:
                points.append(
                    MealPoint(
                        offset_label=offset_label,
                        median_sgv=None,
                        p25=None,
                        p75=None,
                    )
                )

        blocks.append(MealBlock(name=name, hours_label=hours_label, points=points))

    return blocks


def _find_nearest_idx(
    timestamps: list[datetime], target: datetime
) -> int | None:
    """Binary search for nearest timestamp index."""
    if not timestamps:
        return None
    lo, hi = 0, len(timestamps) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if timestamps[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    # Check lo and lo-1
    if lo > 0:
        d1 = abs((timestamps[lo - 1] - target).total_seconds())
        d2 = abs((timestamps[lo] - target).total_seconds())
        return lo - 1 if d1 <= d2 else lo
    return lo


# ── Daily pattern ───────────────────────────────────────────────────────


def _compute_daily_pattern(
    readings: list[GlucoseReading],
    entries: list[LogEntry],
) -> list[DailyPatternPoint]:
    """AGP-like pattern + hourly carbs/insulin averages."""
    import numpy as np

    # Bucket readings by30-min interval
    reading_buckets: list[list[int]] = [[] for _ in range(_AGP_BUCKETS_PER_DAY)]
    for r in readings:
        if r.sgv is not None:
            bi = _bucket_index(_time_of_day_minutes(r.timestamp))
            reading_buckets[bi].append(r.sgv)

    # Bucket carbs and insulin by30-min interval
    carb_buckets: list[list[float]] = [[] for _ in range(_AGP_BUCKETS_PER_DAY)]
    insulin_buckets: list[list[float]] = [[] for _ in range(_AGP_BUCKETS_PER_DAY)]
    for e in entries:
        bi = _bucket_index(_time_of_day_minutes(e.created_at))
        if e.entry_type == LogEntryType.CARBS:
            carb_buckets[bi].append(e.value)
        elif e.entry_type == LogEntryType.INSULIN:
            insulin_buckets[bi].append(e.value)

    # Find period days for averaging
    dates = {_date_key(r.timestamp) for r in readings if r.sgv is not None}
    n_days = max(len(dates), 1)

    points: list[DailyPatternPoint] = []
    for i in range(_AGP_BUCKETS_PER_DAY):
        vals = reading_buckets[i]
        if not vals:
            points.append(
                DailyPatternPoint(
                    time_label=_time_label(i * _AGP_BUCKET_MINUTES),
                    p5=None,
                    p25=None,
                    p50=None,
                    p75=None,
                    p95=None,
                    carbs_avg=None,
                    insulin_avg=None,
                )
            )
            continue

        arr = np.array(vals, dtype=float)
        p5, p25, p50, p75, p95 = np.percentile(arr, [5, 25, 50, 75, 95])

        avg_carbs = (
            round(sum(carb_buckets[i]) / n_days, 1) if carb_buckets[i] else None
        )
        avg_insulin = (
            round(sum(insulin_buckets[i]) / n_days, 1) if insulin_buckets[i] else None
        )

        points.append(
            DailyPatternPoint(
                time_label=_time_label(i * _AGP_BUCKET_MINUTES),
                p5=round(float(p5), 1),
                p25=round(float(p25), 1),
                p50=round(float(p50), 1),
                p75=round(float(p75), 1),
                p95=round(float(p95), 1),
                carbs_avg=avg_carbs,
                insulin_avg=avg_insulin,
            )
        )
    return points


# ── Weekly overview ─────────────────────────────────────────────────────


def _compute_weekly_overview(
    readings_by_date: dict[str, list[GlucoseReading]],
    entries_by_date: dict[str, list[LogEntry]],
) -> list[WeeklyDay]:
    days: list[WeeklyDay] = []
    for dk in sorted(readings_by_date):
        day_readings = readings_by_date[dk]
        ts_first = day_readings[0].timestamp
        sgvs = [r.sgv for r in day_readings if r.sgv is not None]
        day_entries = entries_by_date.get(dk, [])
        carbs = sum(e.value for e in day_entries if e.entry_type == LogEntryType.CARBS)
        insulin = sum(e.value for e in day_entries if e.entry_type == LogEntryType.INSULIN)
        hypo = sum(1 for v in sgvs if v < LOW)

        # Downsample to max ~48 points per day for sparkline
        sorted_r = sorted(day_readings, key=lambda r: r.timestamp)
        step = max(1, len(sorted_r) // 48)
        sparkline = [
            (_to_local(r.timestamp).strftime("%H:%M"), r.sgv)
            for r in sorted_r[::step]
            if r.sgv is not None
        ]

        days.append(
            WeeklyDay(
                date=dk,
                weekday=_weekday_de(ts_first),
                glucose_points=sparkline,
                avg_sgv=round(sum(sgvs) / len(sgvs), 1) if sgvs else None,
                carbs_grams=carbs if carbs > 0 else None,
                insulin_units=insulin if insulin > 0 else None,
                hypo_events=hypo,
            )
        )
    return days


# ── Main entry point ───────────────────────────────────────────────────


def compute_report_data(
    start: datetime,
    end: datetime,
    readings: list[GlucoseReading],
    entries: list[LogEntry],
) -> ReportData:
    """Compute the full AGP report data for a given time range.

    All timestamps are converted to Europe/Berlin for display.
    """
    period_days = max(1, (end - start).days + 1)

    readings_local, entries_local, all_sgv, readings_by_date, entries_by_date = (
        _collect_local(readings, entries)
    )

    glucose_stats = _compute_glucose_stats(all_sgv)

    # Recompute sensor_active_percent with actual readings
    actual_sensor = _compute_sensor_stats(readings_local, period_days)
    glucose_stats = GlucoseStats(
        mean=glucose_stats.mean,
        tir_percent=glucose_stats.tir_percent,
        tir_below=glucose_stats.tir_below,
        tir_above=glucose_stats.tir_above,
        gmi=glucose_stats.gmi,
        cv_percent=glucose_stats.cv_percent,
        std_dev=glucose_stats.std_dev,
        readings=glucose_stats.readings,
        min_val=glucose_stats.min_val,
        max_val=glucose_stats.max_val,
        sensor_active_percent=actual_sensor,
        time_below_54=glucose_stats.time_below_54,
        time_54_70=glucose_stats.time_54_70,
        time_70_180=glucose_stats.time_70_180,
        time_180_250=glucose_stats.time_180_250,
        time_above_250=glucose_stats.time_above_250,
    )

    snapshot = _compute_snapshot(
        readings_local, entries_local, period_days, glucose_stats
    )

    return ReportData(
        period=ReportPeriod(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            num_days=period_days,
        ),
        glucose_stats=glucose_stats,
        agp_curve=_compute_agp_curve(readings_local),
        daily_profiles=_compute_daily_profiles(readings_by_date, entries_by_date),
        monthly_overview=_compute_monthly_overview(readings_by_date, entries_by_date),
        daily_protocols=_compute_daily_protocols(readings_by_date),
        snapshot=snapshot,
        meal_profile=_compute_meal_profile(readings_local, entries_local),
        daily_pattern=_compute_daily_pattern(readings_local, entries_local),
        weekly_overview=_compute_weekly_overview(readings_by_date, entries_by_date),
    )
