"""AGP report aggregation for Europe/Berlin calendar days.

The service is deliberately independent of Flask.  Callers provide the selected
calendar dates and already-loaded ORM records; all timestamps returned to the
client are converted to Europe/Berlin.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from math import isfinite
from statistics import median
from zoneinfo import ZoneInfo

from bgmon_api.models import MAX_LOG_ENTRY_VALUE, GlucoseReading, LogEntry, LogEntryType

LOCAL_TZ = ZoneInfo("Europe/Berlin")

# TIR thresholds (mg/dL), matching the FreeStyle defaults.
LOW = 70
HIGH = 180
CRITICAL_LOW = 54
CRITICAL_HIGH = 250

# AGP percentile buckets: 30-minute intervals over 24h.
_AGP_BUCKET_MINUTES = 30
_AGP_BUCKETS_PER_DAY = 24 * 60 // _AGP_BUCKET_MINUTES

# Raw daily traces use elapsed 10-minute buckets from Berlin local midnight.
# The combined valid-extrema and compression-marker payload is capped at 300
# points. A 25-hour autumn fallback day has 150 elapsed buckets.
_TRACE_BUCKET_MINUTES = 10
_TRACE_MAX_POINTS_PER_DAY = 300
# Keep at most one explicit compression marker per elapsed trace bucket.
_TRACE_MAX_COMPRESSION_MARKERS_PER_DAY = 150

# A gap longer than this cannot establish that two low observations are one event.
_LOW_EPISODE_MAX_GAP = timedelta(minutes=15)

# Detail rows are bounded for API/PDF payloads; summary counts retain all events.
_MAX_LOW_EVENT_DETAILS = 100

# Coverage intervals use the observed cadence, capped so sparse observations do
# not turn a long data outage into apparent sensor coverage.
_DEFAULT_COVERAGE_CADENCE = timedelta(minutes=5)
_MAX_COVERAGE_CADENCE = timedelta(minutes=15)

# Protocol charts show only a bounded marker subset, avoiding unbounded SVG and
# JSON payloads for a busy 90-day report. Marker notes are shortened as well.
_MAX_LOG_MARKERS_PER_DAY = 50
_MAX_LOG_MARKER_NOTE_CHARS = 240

# Meal time blocks in local hours.  Night wraps from 22:00 through 04:00.
_MEAL_BLOCKS = {
    "morning": (4, 10),
    "midday": (10, 16),
    "evening": (16, 22),
    "night": (22, 4),
}


# ── Data contract ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ReportPeriod:
    """Selected local calendar-date range."""

    start: str
    end: str
    num_days: int


@dataclass(frozen=True, slots=True)
class GlucoseStats:
    """Aggregate glucose statistics for the selected period."""

    mean: float | None
    tir_percent: float | None
    tir_below: float | None
    tir_above: float | None
    gmi: float | None
    gmi_mmol_mol: int | None
    cv_percent: float | None
    std_dev: float | None
    readings: int
    min_val: float | None
    max_val: float | None
    data_coverage_percent: float
    time_below_54_percent: float | None
    time_54_70_percent: float | None
    time_70_180_percent: float | None
    time_180_250_percent: float | None
    time_above_250_percent: float | None


@dataclass(frozen=True, slots=True)
class AGPPoint:
    """Percentile values for a local 30-minute time-of-day bucket."""

    bucket_index: int
    time_label: str
    p5: float | None
    p25: float | None
    p50: float | None
    p75: float | None
    p95: float | None


@dataclass(frozen=True, slots=True)
class GlucosePoint:
    """A raw glucose observation with a display-local ISO timestamp."""

    timestamp: str
    sgv: int
    trend: int | None
    direction: str | None
    is_compression_low: bool


@dataclass(frozen=True, slots=True)
class DailyProfile:
    """One selected local day, including glucose points and treatment totals."""

    date: str
    weekday: str
    readings: list[GlucosePoint]
    avg: float | None
    carbs_total: float
    rapid_insulin_total: float
    basal_insulin_total: float
    total_insulin: float
    low_events: int
    data_coverage_percent: float


@dataclass(frozen=True, slots=True)
class DayOverview:
    """Calendar overview data for one selected local day."""

    date: str
    weekday: str
    avg_sgv: float | None
    carbs_total: float
    rapid_insulin_total: float
    basal_insulin_total: float
    total_insulin: float
    low_events: int
    reading_count: int
    data_coverage_percent: float


@dataclass(frozen=True, slots=True)
class IntervalMinMax:
    """Min/max glucose for one local one-hour interval."""

    hour: int
    time_start: str
    time_end: str
    min_val: int | None
    max_val: int | None


@dataclass(frozen=True, slots=True)
class LogMarker:
    """A local-time marker used to annotate a daily glucose trace."""

    timestamp: str
    kind: str
    value: float
    unit: str
    notes: str | None


@dataclass(frozen=True, slots=True)
class DayProtocol:
    """Hourly glucose ranges and log markers for one day."""

    date: str
    weekday: str
    intervals: list[IntervalMinMax]
    markers: list[LogMarker]
    marker_count: int
    markers_truncated: bool


@dataclass(frozen=True, slots=True)
class LowGlucoseEvent:
    """A timestamp-aware hypoglycemic episode, represented in local time."""

    date: str
    time: str
    timestamp: str
    sgv: int
    duration_minutes: int


@dataclass(frozen=True, slots=True)
class CoveragePoint:
    """Aggregate coverage for a local two-hour time-of-day interval."""

    time_start: str
    time_end: str
    data_coverage_percent: float


@dataclass(frozen=True, slots=True)
class ReportSnapshot:
    """Period summary used by the compact report snapshot."""

    mean_sgv: float | None
    gmi: float | None
    gmi_mmol_mol: int | None
    tir_percent: float | None
    below_percent: float | None
    above_percent: float | None
    low_events_count: int
    low_events_avg_duration_minutes: float | None
    data_coverage_percent: float
    carbs_daily_avg: float
    rapid_insulin_daily_avg: float
    basal_insulin_daily_avg: float
    total_insulin_daily_avg: float
    coverage_profile: list[CoveragePoint]
    low_events: list[LowGlucoseEvent]
    low_events_truncated: bool


@dataclass(frozen=True, slots=True)
class MealPoint:
    """Glucose percentile values relative to a logged meal."""

    offset_label: str
    median_sgv: float | None
    p25: float | None
    p75: float | None


@dataclass(frozen=True, slots=True)
class MealBlock:
    """Meal-relative profile for a named local-time block."""

    name: str
    hours_label: str
    points: list[MealPoint]


@dataclass(frozen=True, slots=True)
class DailyPatternPoint:
    """AGP percentile values plus selected-day-average treatment amounts."""

    time_label: str
    p5: float | None
    p25: float | None
    p50: float | None
    p75: float | None
    p95: float | None
    carbs_avg: float
    rapid_insulin_avg: float
    basal_insulin_avg: float


@dataclass(frozen=True, slots=True)
class WeeklyDay:
    """One selected day for a weekly-style overview."""

    date: str
    weekday: str
    avg_sgv: float | None
    carbs_total: float
    rapid_insulin_total: float
    basal_insulin_total: float
    total_insulin: float
    low_events: int
    reading_count: int
    data_coverage_percent: float


@dataclass(slots=True)
class ReportData:
    """Complete, JSON-serializable AGP report payload."""

    patient_name: str
    generated_at: str
    timezone: str
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


@dataclass(frozen=True, slots=True)
class _ObservationSpan:
    """A glucose value held over a clinically observed, capped time interval."""

    sgv: int
    start: datetime
    end: datetime
    local_date_key: str
    local_minutes: int


@dataclass(frozen=True, slots=True)
class _ReadingSample:
    """Cached report-relevant fields from a raw glucose model instance."""

    raw: GlucoseReading
    timestamp: datetime
    local_timestamp: datetime
    date_key: str
    local_minutes: int
    trace_bucket_index: int
    sgv: int
    trend: int | None
    direction: str | None
    source: str
    is_compression_low: bool


@dataclass(slots=True)
class _SpanIndex:
    """Observed-time spans indexed for report views without repeated global scans."""

    start: datetime
    end: datetime
    by_date: dict[str, list[_ObservationSpan]]
    coverage_seconds_by_date: dict[str, float]
    weighted_sgv_seconds_by_date: dict[str, float]
    coverage_seconds_by_two_hour_bucket: list[float]
    agp_buckets: list[list[tuple[int, float]]]
    total_coverage_seconds: float
    weighted_sgv_seconds: float
    weighted_sgv_squared_seconds: float
    band_seconds: tuple[float, float, float, float, float]
    min_sgv: int | None
    max_sgv: int | None
    span_count: int


# ── Timezone and date helpers ────────────────────────────────────────────


def _as_utc(timestamp: datetime) -> datetime:
    """Return a timestamp as an aware UTC datetime.

    Database timestamps are timezone-aware. Treating an unexpected naive value
    as UTC keeps pure aggregation deterministic for imported legacy records.
    """
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def _to_local(timestamp: datetime) -> datetime:
    """Convert a timestamp to Europe/Berlin."""
    return _as_utc(timestamp).astimezone(LOCAL_TZ)


def _display_timestamp(timestamp: datetime) -> str:
    """Return an ISO timestamp with the Europe/Berlin offset for the client."""
    return _to_local(timestamp).isoformat(timespec="seconds")


def _local_date(value: date | datetime) -> date:
    """Interpret datetimes in Europe/Berlin and leave date inputs untouched."""
    if isinstance(value, datetime):
        return _to_local(value).date()
    return value


def _local_midnight(day: date) -> datetime:
    """Return the first instant of a Berlin calendar day."""
    return datetime.combine(day, time.min, tzinfo=LOCAL_TZ)


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    """Return UTC bounds for the half-open local calendar day."""
    return (
        _local_midnight(day).astimezone(UTC),
        _local_midnight(day + timedelta(days=1)).astimezone(UTC),
    )


def _date_key(timestamp: datetime) -> str:
    """Return the local YYYY-MM-DD date key for a timestamp."""
    return _to_local(timestamp).date().isoformat()


def _reading_sample(reading: GlucoseReading) -> _ReadingSample:
    """Cache UTC/local fields once to avoid repeated ORM and timezone access."""
    timestamp = _as_utc(reading.timestamp)
    local_timestamp = timestamp.astimezone(LOCAL_TZ)
    local_midnight = _local_midnight(local_timestamp.date()).astimezone(UTC)
    return _ReadingSample(
        raw=reading,
        timestamp=timestamp,
        local_timestamp=local_timestamp,
        date_key=local_timestamp.date().isoformat(),
        local_minutes=local_timestamp.hour * 60 + local_timestamp.minute,
        # UTC elapsed time distinguishes the two 02:xx folds on DST fallback.
        trace_bucket_index=int(
            (timestamp - local_midnight).total_seconds() // (_TRACE_BUCKET_MINUTES * 60)
        ),
        sgv=reading.sgv,
        trend=reading.trend,
        direction=reading.direction,
        source=reading.source,
        is_compression_low=bool(reading.is_compression_low),
    )


def _weekday_de(day: date) -> str:
    """Return the abbreviated German weekday name for a local date."""
    return ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")[day.weekday()]


def _time_of_day_minutes(timestamp: datetime) -> int:
    """Return the local minutes elapsed since midnight."""
    local_timestamp = _to_local(timestamp)
    return local_timestamp.hour * 60 + local_timestamp.minute


def _time_label(minutes: int) -> str:
    """Format local minutes since midnight as HH:MM."""
    hours, remainder = divmod(minutes, 60)
    return f"{hours:02d}:{remainder:02d}"


def _bucket_index(minutes: int) -> int:
    """Map local minutes since midnight to an AGP bucket index."""
    return min(minutes // _AGP_BUCKET_MINUTES, _AGP_BUCKETS_PER_DAY - 1)


def _selected_dates(start: date | datetime, end: date | datetime) -> list[date]:
    """Build the inclusive local-date spine for the requested report period."""
    start_day = _local_date(start)
    end_day = _local_date(end)
    if start_day > end_day:
        raise ValueError("report start date must not be after end date")
    return [start_day + timedelta(days=offset) for offset in range((end_day - start_day).days + 1)]


# ── Shared aggregation helpers ───────────────────────────────────────────


def _collect_local(
    readings: list[GlucoseReading],
    entries: list[LogEntry],
    selected_date_keys: set[str],
    start: datetime,
    effective_end: datetime,
) -> tuple[
    list[_ReadingSample],
    list[LogEntry],
    int,
    dict[str, list[_ReadingSample]],
    dict[str, list[LogEntry]],
]:
    """Separate selected raw readings from selected clinical aggregate inputs."""
    readings_by_date: dict[str, list[_ReadingSample]] = {}
    entries_by_date: dict[str, list[LogEntry]] = {}
    selected_readings: list[_ReadingSample] = []
    selected_entries: list[LogEntry] = []
    clinical_reading_count = 0

    samples = sorted(
        (_reading_sample(reading) for reading in readings if reading.sgv is not None),
        key=lambda sample: sample.timestamp,
    )
    for sample in samples:
        if not start <= sample.timestamp < effective_end:
            continue
        if sample.date_key not in selected_date_keys:
            continue
        readings_by_date.setdefault(sample.date_key, []).append(sample)
        selected_readings.append(sample)
        if not sample.is_compression_low:
            clinical_reading_count += 1

    for entry in entries:
        # PostgreSQL Float permits NaN and Infinity. Ignore malformed legacy
        # entries so one bad value cannot make the complete report invalid JSON.
        if not isfinite(entry.value) or abs(entry.value) > MAX_LOG_ENTRY_VALUE:
            continue
        if not start <= _as_utc(entry.created_at) < effective_end:
            continue
        day_key = _date_key(entry.created_at)
        if day_key not in selected_date_keys:
            continue
        entries_by_date.setdefault(day_key, []).append(entry)
        selected_entries.append(entry)

    return (
        selected_readings,
        selected_entries,
        clinical_reading_count,
        readings_by_date,
        entries_by_date,
    )


def _entry_totals(entries: list[LogEntry]) -> tuple[float, float, float, float]:
    """Return carbohydrate, rapid, basal, and combined insulin totals."""
    carbs = sum(_carb_grams(entry) for entry in entries if entry.entry_type == LogEntryType.CARBS)
    rapid = sum(entry.value for entry in entries if entry.entry_type == LogEntryType.INSULIN)
    basal = sum(entry.value for entry in entries if entry.entry_type == LogEntryType.BASAL)
    return round(carbs, 1), round(rapid, 1), round(basal, 1), round(rapid + basal, 1)


def _carb_grams(entry: LogEntry) -> float:
    """Normalize logged carbohydrate units to grams for the report.

    The log form stores bread units (KE), where one KE equals ten grams. Older
    imported entries can already be stored as grams and therefore remain unchanged.
    """
    return entry.value * 10 if entry.unit.strip().lower() in {"ke", "khe"} else entry.value


def _glucose_point(reading: _ReadingSample) -> GlucosePoint:
    """Serialize one raw glucose reading for a display-local trace."""
    return GlucosePoint(
        timestamp=reading.local_timestamp.isoformat(timespec="seconds"),
        sgv=reading.sgv,
        trend=reading.trend,
        direction=reading.direction,
        is_compression_low=reading.is_compression_low,
    )


def _evenly_spaced_samples(
    samples: list[_ReadingSample], maximum: int
) -> list[_ReadingSample]:
    """Keep timestamp-spaced samples while preserving the global extrema."""
    if len(samples) <= maximum:
        return samples
    if maximum <= 0:
        return []

    minimum = min(samples, key=lambda sample: sample.sgv)
    maximum_sample = max(samples, key=lambda sample: sample.sgv)
    retained_by_id = {id(minimum): minimum, id(maximum_sample): maximum_sample}
    if len(retained_by_id) >= maximum:
        return list(retained_by_id.values())[:maximum]

    remaining = [sample for sample in samples if id(sample) not in retained_by_id]
    available = maximum - len(retained_by_id)
    for index in range(available):
        sample = remaining[index * len(remaining) // available]
        retained_by_id[id(sample)] = sample
    return sorted(retained_by_id.values(), key=lambda sample: sample.timestamp)


def _glucose_points(readings: list[_ReadingSample]) -> list[GlucosePoint]:
    """Serialize selected raw readings, downsampling dense traces by extrema.

    Every elapsed 10-minute bucket since Berlin local midnight keeps its earliest
    valid minimum and maximum glucose point, plus the earliest compression marker.
    Compression markers are prioritized, then valid extrema fill the remaining
    combined point budget. This preserves artifact visibility and prevents a
    dense mixed trace from exceeding the API and SVG payload cap.
    """
    sorted_readings = sorted(readings, key=lambda reading: reading.timestamp)
    compression_count = sum(reading.is_compression_low for reading in sorted_readings)
    if (
        len(sorted_readings) <= _TRACE_MAX_POINTS_PER_DAY
        and compression_count <= _TRACE_MAX_COMPRESSION_MARKERS_PER_DAY
    ):
        return [_glucose_point(reading) for reading in sorted_readings]

    buckets: dict[int, list[_ReadingSample]] = defaultdict(list)
    for reading in sorted_readings:
        buckets[reading.trace_bucket_index].append(reading)

    valid_extrema: list[_ReadingSample] = []
    compression_markers: list[_ReadingSample] = []
    for bucket_readings in buckets.values():
        valid_readings = [reading for reading in bucket_readings if not reading.is_compression_low]
        if valid_readings:
            minimum = min(valid_readings, key=lambda reading: reading.sgv)
            maximum = max(valid_readings, key=lambda reading: reading.sgv)
            valid_extrema.extend({id(minimum): minimum, id(maximum): maximum}.values())
        compression_marker = next(
            (reading for reading in bucket_readings if reading.is_compression_low),
            None,
        )
        if compression_marker is not None:
            compression_markers.append(compression_marker)

    retained = compression_markers[:_TRACE_MAX_COMPRESSION_MARKERS_PER_DAY]
    valid_budget = _TRACE_MAX_POINTS_PER_DAY - len(retained)
    retained.extend(_evenly_spaced_samples(valid_extrema, valid_budget))
    retained_by_id = {id(reading): reading for reading in retained}
    return [
        _glucose_point(reading)
        for reading in sorted(retained_by_id.values(), key=lambda reading: reading.timestamp)
    ]


# ── Observed-time coverage and weighting ─────────────────────────────────


def _cadence_by_reading(readings: list[_ReadingSample]) -> dict[int, timedelta]:
    """Infer contiguous cadence regimes independently for each source.

    A >=2x cadence change starts a new regime only when the following interval
    remains comparable to that candidate. This keeps a same-source 15-minute
    historical run separate from a sustained 1-minute live run, while a lone
    5m -> 15m -> 5m poll is treated as jitter. Gaps above 15 minutes split
    runs, so earlier points never borrow cadence from a later run.
    """
    readings_by_source: dict[str, list[_ReadingSample]] = defaultdict(list)
    for reading in readings:
        readings_by_source[reading.source].append(reading)

    cadences: dict[int, timedelta] = {}

    def assign_run(run: list[_ReadingSample]) -> None:
        """Assign only run-local cadence so an outage cannot borrow future data."""
        if len(run) == 1:
            cadences[id(run[0])] = _DEFAULT_COVERAGE_CADENCE
            return

        deltas = [
            later.timestamp - earlier.timestamp
            for earlier, later in zip(run, run[1:], strict=False)
        ]
        regime_start = 0
        regime_baseline = deltas[0]
        for edge_index in range(1, len(deltas)):
            current = deltas[edge_index]
            next_delta = deltas[edge_index + 1] if edge_index + 1 < len(deltas) else None
            differs = current >= regime_baseline * 2 or regime_baseline >= current * 2
            is_sustained = next_delta is not None and not (
                next_delta >= current * 2 or current >= next_delta * 2
            )
            if differs and is_sustained:
                cadence = min(median(deltas[regime_start:edge_index]), _MAX_COVERAGE_CADENCE)
                for reading in run[regime_start:edge_index]:
                    cadences[id(reading)] = cadence
                regime_start = edge_index
                regime_baseline = current
            elif not differs:
                regime_baseline = current

        cadence = min(median(deltas[regime_start:]), _MAX_COVERAGE_CADENCE)
        for reading in run[regime_start:]:
            cadences[id(reading)] = cadence

    for source_readings in readings_by_source.values():
        source_readings.sort(key=lambda reading: reading.timestamp)
        run_start = 0
        for index in range(1, len(source_readings)):
            gap = source_readings[index].timestamp - source_readings[index - 1].timestamp
            if gap <= timedelta(0) or gap > _MAX_COVERAGE_CADENCE:
                assign_run(source_readings[run_start:index])
                run_start = index
        assign_run(source_readings[run_start:])
    return cadences


def _observation_spans(
    readings: list[_ReadingSample],
    start: datetime,
    end: datetime,
) -> list[_ObservationSpan]:
    """Build non-overlapping, cadence-clipped spans from glucose observations.

    A reading represents its glucose state only until the next reading or the
    inferred normal cadence, whichever comes first. Therefore long polling
    gaps are absent from both coverage and glucose statistics.
    """
    sorted_readings = readings
    cadence_by_reading = _cadence_by_reading(sorted_readings)
    spans: list[_ObservationSpan] = []
    for index, reading in enumerate(sorted_readings):
        reading_start = reading.timestamp
        next_start = (
            sorted_readings[index + 1].timestamp
            if index + 1 < len(sorted_readings)
            else reading_start + cadence_by_reading[id(reading)]
        )
        span_start = max(reading_start, start)
        span_end = min(reading_start + cadence_by_reading[id(reading)], next_start, end)
        # Compression lows still terminate the preceding observation, but never
        # contribute glucose-state time themselves.
        if span_start < span_end and not reading.is_compression_low:
            if span_start == reading_start:
                local_date_key = reading.date_key
                local_minutes = reading.local_minutes
            else:
                local_start = span_start.astimezone(LOCAL_TZ)
                local_date_key = local_start.date().isoformat()
                local_minutes = local_start.hour * 60 + local_start.minute
            spans.append(
                _ObservationSpan(
                    reading.sgv,
                    span_start,
                    span_end,
                    local_date_key,
                    local_minutes,
                )
            )
    return spans


def _next_agp_bucket_boundary(timestamp: datetime) -> datetime:
    """Return the next 30-minute UTC boundary used by Berlin AGP buckets.

    Europe/Berlin offsets are whole hours and DST changes occur on an exact UTC
    hour. Therefore local half-hour boundaries are also UTC half-hour boundaries,
    including both repeated and skipped local DST hours.
    """
    base = timestamp.replace(second=0, microsecond=0)
    return base + timedelta(minutes=_AGP_BUCKET_MINUTES - base.minute % _AGP_BUCKET_MINUTES)


def _build_span_index(
    observation_spans: list[_ObservationSpan], start: datetime, end: datetime
) -> _SpanIndex:
    """Split spans once for day coverage, two-hour coverage, and AGP buckets."""
    by_date: dict[str, list[_ObservationSpan]] = defaultdict(list)
    coverage_seconds_by_date: dict[str, float] = defaultdict(float)
    weighted_sgv_seconds_by_date: dict[str, float] = defaultdict(float)
    coverage_seconds_by_two_hour_bucket = [0.0] * 12
    agp_buckets: list[list[tuple[int, float]]] = [[] for _ in range(_AGP_BUCKETS_PER_DAY)]
    total_coverage_seconds = 0.0
    weighted_sgv_seconds = 0.0
    weighted_sgv_squared_seconds = 0.0
    band_seconds = [0.0] * 5
    min_sgv: int | None = None
    max_sgv: int | None = None

    for span in observation_spans:
        cursor = span.start
        local_minutes = span.local_minutes
        date_key = span.local_date_key
        while cursor < span.end:
            segment_end = min(span.end, _next_agp_bucket_boundary(cursor))
            seconds = (segment_end - cursor).total_seconds()
            if seconds <= 0:
                break
            segment = _ObservationSpan(span.sgv, cursor, segment_end, date_key, local_minutes)
            by_date[date_key].append(segment)
            coverage_seconds_by_date[date_key] += seconds
            weighted_sgv_seconds_by_date[date_key] += span.sgv * seconds
            coverage_seconds_by_two_hour_bucket[local_minutes // 120] += seconds
            agp_buckets[local_minutes // _AGP_BUCKET_MINUTES].append((span.sgv, seconds))
            total_coverage_seconds += seconds
            weighted_sgv_seconds += span.sgv * seconds
            weighted_sgv_squared_seconds += span.sgv**2 * seconds
            if span.sgv < CRITICAL_LOW:
                band_seconds[0] += seconds
            elif span.sgv < LOW:
                band_seconds[1] += seconds
            elif span.sgv <= HIGH:
                band_seconds[2] += seconds
            elif span.sgv <= CRITICAL_HIGH:
                band_seconds[3] += seconds
            else:
                band_seconds[4] += seconds
            min_sgv = span.sgv if min_sgv is None else min(min_sgv, span.sgv)
            max_sgv = span.sgv if max_sgv is None else max(max_sgv, span.sgv)
            cursor = segment_end
            if cursor < span.end:
                local_cursor = cursor.astimezone(LOCAL_TZ)
                date_key = local_cursor.date().isoformat()
                local_minutes = local_cursor.hour * 60 + local_cursor.minute

    return _SpanIndex(
        start=start,
        end=end,
        by_date=dict(by_date),
        coverage_seconds_by_date=dict(coverage_seconds_by_date),
        weighted_sgv_seconds_by_date=dict(weighted_sgv_seconds_by_date),
        coverage_seconds_by_two_hour_bucket=coverage_seconds_by_two_hour_bucket,
        agp_buckets=agp_buckets,
        total_coverage_seconds=total_coverage_seconds,
        weighted_sgv_seconds=weighted_sgv_seconds,
        weighted_sgv_squared_seconds=weighted_sgv_squared_seconds,
        band_seconds=(
            band_seconds[0],
            band_seconds[1],
            band_seconds[2],
            band_seconds[3],
            band_seconds[4],
        ),
        min_sgv=min_sgv,
        max_sgv=max_sgv,
        span_count=len(observation_spans),
    )


def _coverage_profile(span_index: _SpanIndex, selected_days: list[date]) -> list[CoveragePoint]:
    """Aggregate indexed coverage into twelve local two-hour intervals."""
    points: list[CoveragePoint] = []
    for hour in range(0, 24, 2):
        available = 0.0
        for day in selected_days:
            local_start = datetime.combine(day, time(hour=hour), tzinfo=LOCAL_TZ)
            if hour == 22:
                local_end = _local_midnight(day + timedelta(days=1))
            else:
                local_end = datetime.combine(day, time(hour=hour + 2), tzinfo=LOCAL_TZ)
            bucket_start = max(local_start.astimezone(UTC), span_index.start)
            bucket_end = min(local_end.astimezone(UTC), span_index.end)
            if bucket_start < bucket_end:
                available += (bucket_end - bucket_start).total_seconds()
        points.append(
            CoveragePoint(
                time_start=_time_label(hour * 60),
                time_end=_time_label((hour + 2) % 24 * 60),
                data_coverage_percent=(
                    round(
                        span_index.coverage_seconds_by_two_hour_bucket[hour // 2] / available * 100,
                        1,
                    )
                    if available
                    else 0.0
                ),
            )
        )
    return points


def _compute_glucose_stats(
    selected_clinical_reading_count: int,
    span_index: _SpanIndex,
    data_coverage_percent: float,
) -> GlucoseStats:
    """Compute glucose metrics from the already indexed observed-time spans."""
    if span_index.total_coverage_seconds == 0:
        return GlucoseStats(
            mean=None,
            tir_percent=None,
            tir_below=None,
            tir_above=None,
            gmi=None,
            gmi_mmol_mol=None,
            cv_percent=None,
            std_dev=None,
            readings=selected_clinical_reading_count,
            min_val=None,
            max_val=None,
            data_coverage_percent=data_coverage_percent,
            time_below_54_percent=None,
            time_54_70_percent=None,
            time_70_180_percent=None,
            time_180_250_percent=None,
            time_above_250_percent=None,
        )

    total_seconds = span_index.total_coverage_seconds
    mean_value = span_index.weighted_sgv_seconds / total_seconds
    variance = max(
        0.0,
        span_index.weighted_sgv_squared_seconds / total_seconds - mean_value**2,
    )
    std_dev = variance**0.5
    band_percentages = tuple(
        round(seconds / total_seconds * 100, 1) for seconds in span_index.band_seconds
    )
    gmi = round(3.31 + 0.02392 * mean_value, 1) if mean_value is not None else None
    tir_below = round(
        (span_index.band_seconds[0] + span_index.band_seconds[1]) / total_seconds * 100,
        1,
    )
    tir_above = round(
        (span_index.band_seconds[3] + span_index.band_seconds[4]) / total_seconds * 100,
        1,
    )
    tir_percent = band_percentages[2]
    return GlucoseStats(
        mean=round(mean_value, 1) if mean_value is not None else None,
        tir_percent=tir_percent,
        tir_below=tir_below,
        tir_above=tir_above,
        gmi=gmi,
        # IFCC conversion is intentionally (GMI - 2.15) / 0.0915, without +13.5.
        gmi_mmol_mol=round((gmi - 2.15) / 0.0915) if gmi is not None else None,
        cv_percent=(
            round(std_dev / mean_value * 100, 1)
            if span_index.span_count > 1 and mean_value != 0
            else None
        ),
        std_dev=round(std_dev, 1) if std_dev is not None else None,
        readings=selected_clinical_reading_count,
        min_val=span_index.min_sgv,
        max_val=span_index.max_sgv,
        data_coverage_percent=data_coverage_percent,
        time_below_54_percent=band_percentages[0],
        time_54_70_percent=band_percentages[1],
        time_70_180_percent=band_percentages[2],
        time_180_250_percent=band_percentages[3],
        time_above_250_percent=band_percentages[4],
    )


def _weighted_percentiles(
    weighted_values: list[tuple[int, float]],
) -> tuple[float | None, float | None, float | None, float | None, float | None]:
    """Return inverse-CDF AGP percentiles from duration-weighted glucose values."""
    if not weighted_values:
        return None, None, None, None, None
    percentiles = (5, 25, 50, 75, 95)
    total_seconds = sum(weight for _, weight in weighted_values)
    targets = [total_seconds * percentile / 100 for percentile in percentiles]
    results: list[float] = []
    cumulative_seconds = 0.0
    target_index = 0
    sorted_values = sorted(weighted_values)
    for value, weight in sorted_values:
        cumulative_seconds += weight
        while target_index < len(targets) and cumulative_seconds >= targets[target_index]:
            results.append(float(value))
            target_index += 1
    results.extend([float(sorted_values[-1][0])] * (len(percentiles) - len(results)))
    return results[0], results[1], results[2], results[3], results[4]


def _compute_agp_curve(
    percentiles_by_bucket: list[
        tuple[float | None, float | None, float | None, float | None, float | None]
    ],
) -> list[AGPPoint]:
    """Compute duration-weighted AGP percentiles by local 30-minute bucket."""
    points: list[AGPPoint] = []
    for index, percentiles in enumerate(percentiles_by_bucket):
        if percentiles[0] is None:
            points.append(
                AGPPoint(
                    bucket_index=index,
                    time_label=_time_label(index * _AGP_BUCKET_MINUTES),
                    p5=None,
                    p25=None,
                    p50=None,
                    p75=None,
                    p95=None,
                )
            )
            continue
        p5, p25, p50, p75, p95 = percentiles
        points.append(
            AGPPoint(
                bucket_index=index,
                time_label=_time_label(index * _AGP_BUCKET_MINUTES),
                p5=p5,
                p25=p25,
                p50=p50,
                p75=p75,
                p95=p95,
            )
        )
    return points


# ── Timestamp-aware low episodes ─────────────────────────────────────────


def _append_low_event(
    events: list[LowGlucoseEvent],
    start: datetime,
    end: datetime,
    minimum_sgv: int,
) -> None:
    """Append a local-display low event from its observed start/end bounds."""
    local_start = _to_local(start)
    duration = max(1, int((end - start).total_seconds() // 60))
    events.append(
        LowGlucoseEvent(
            date=local_start.date().isoformat(),
            time=local_start.strftime("%H:%M"),
            timestamp=local_start.isoformat(timespec="seconds"),
            sgv=minimum_sgv,
            duration_minutes=duration,
        )
    )


def _compute_low_events(readings: list[_ReadingSample]) -> list[LowGlucoseEvent]:
    """Find low episodes split by recovery readings or gaps over 15 minutes.

    A low sequence can only remain one episode when each consecutive low reading
    is at most ``_LOW_EPISODE_MAX_GAP`` apart. A recovery reading closes the
    episode at its timestamp when it is timely; otherwise the final low reading
    is the conservative observed endpoint.
    """
    sorted_readings = readings
    events: list[LowGlucoseEvent] = []
    low_start: datetime | None = None
    last_low: datetime | None = None
    minimum_sgv: int | None = None

    for reading in sorted_readings:
        timestamp = reading.timestamp
        if reading.is_compression_low:
            # A likely compression artifact carries no clinical glucose state and
            # must not connect a low episode across an invalid observation.
            if low_start is not None and last_low is not None and minimum_sgv is not None:
                _append_low_event(events, low_start, last_low, minimum_sgv)
                low_start = None
                last_low = None
                minimum_sgv = None
            continue
        if reading.sgv < LOW:
            if low_start is None:
                low_start = timestamp
                last_low = timestamp
                minimum_sgv = reading.sgv
                continue
            if last_low is not None and timestamp - last_low <= _LOW_EPISODE_MAX_GAP:
                last_low = timestamp
                minimum_sgv = min(
                    minimum_sgv if minimum_sgv is not None else reading.sgv,
                    reading.sgv,
                )
                continue

            _append_low_event(
                events,
                low_start,
                last_low or low_start,
                minimum_sgv if minimum_sgv is not None else reading.sgv,
            )
            low_start = timestamp
            last_low = timestamp
            minimum_sgv = reading.sgv
            continue

        if low_start is not None and last_low is not None and minimum_sgv is not None:
            event_end = timestamp if timestamp - last_low <= _LOW_EPISODE_MAX_GAP else last_low
            _append_low_event(events, low_start, event_end, minimum_sgv)
            low_start = None
            last_low = None
            minimum_sgv = None

    if low_start is not None and last_low is not None and minimum_sgv is not None:
        _append_low_event(events, low_start, last_low, minimum_sgv)
    return events


def _events_by_date(events: list[LowGlucoseEvent]) -> dict[str, list[LowGlucoseEvent]]:
    """Group episodes by the local date on which each episode started."""
    grouped: dict[str, list[LowGlucoseEvent]] = {}
    for event in events:
        grouped.setdefault(event.date, []).append(event)
    return grouped


# ── Date-spined daily views ──────────────────────────────────────────────


def _daily_coverage_percent(span_index: _SpanIndex, day: date) -> float:
    """Return data coverage for one local calendar day."""
    day_start, day_end = _day_bounds(day)
    start = max(day_start, span_index.start)
    end = min(day_end, span_index.end)
    total_seconds = (end - start).total_seconds()
    if total_seconds <= 0:
        return 0.0
    return round(
        span_index.coverage_seconds_by_date.get(day.isoformat(), 0.0) / total_seconds * 100,
        1,
    )


def _compute_daily_profiles(
    selected_days: list[date],
    entries_by_date: dict[str, list[LogEntry]],
    events_by_date: dict[str, list[LowGlucoseEvent]],
    span_index: _SpanIndex,
    trace_points_by_date: dict[str, list[GlucosePoint]],
) -> list[DailyProfile]:
    """Build one profile for every selected date, including no-data dates."""
    profiles: list[DailyProfile] = []
    for day in selected_days:
        day_key = day.isoformat()
        day_spans = span_index.by_date.get(day_key, [])
        carbs, rapid, basal, total = _entry_totals(entries_by_date.get(day_key, []))
        profiles.append(
            DailyProfile(
                date=day_key,
                weekday=_weekday_de(day),
                readings=trace_points_by_date.get(day_key, []),
                avg=(
                    round(
                        span_index.weighted_sgv_seconds_by_date.get(day_key, 0.0)
                        / span_index.coverage_seconds_by_date[day_key],
                        1,
                    )
                    if day_spans
                    else None
                ),
                carbs_total=carbs,
                rapid_insulin_total=rapid,
                basal_insulin_total=basal,
                total_insulin=total,
                low_events=len(events_by_date.get(day_key, [])),
                data_coverage_percent=_daily_coverage_percent(span_index, day),
            )
        )
    return profiles


def _compute_monthly_overview(
    selected_days: list[date],
    readings_by_date: dict[str, list[_ReadingSample]],
    entries_by_date: dict[str, list[LogEntry]],
    events_by_date: dict[str, list[LowGlucoseEvent]],
    span_index: _SpanIndex,
) -> list[DayOverview]:
    """Build calendar overview rows for every selected local date."""
    overview: list[DayOverview] = []
    for day in selected_days:
        day_key = day.isoformat()
        day_readings = readings_by_date.get(day_key, [])
        day_spans = span_index.by_date.get(day_key, [])
        carbs, rapid, basal, total = _entry_totals(entries_by_date.get(day_key, []))
        overview.append(
            DayOverview(
                date=day_key,
                weekday=_weekday_de(day),
                avg_sgv=(
                    round(
                        span_index.weighted_sgv_seconds_by_date.get(day_key, 0.0)
                        / span_index.coverage_seconds_by_date[day_key],
                        1,
                    )
                    if day_spans
                    else None
                ),
                carbs_total=carbs,
                rapid_insulin_total=rapid,
                basal_insulin_total=basal,
                total_insulin=total,
                low_events=len(events_by_date.get(day_key, [])),
                reading_count=sum(not reading.is_compression_low for reading in day_readings),
                data_coverage_percent=_daily_coverage_percent(span_index, day),
            )
        )
    return overview


def _marker_kind(entry: LogEntry) -> str | None:
    """Map stored log entry types to explicit report marker kinds."""
    marker_kinds = {
        LogEntryType.CARBS: "carbs",
        LogEntryType.INSULIN: "rapid_insulin",
        LogEntryType.BASAL: "basal",
        LogEntryType.NOTE: "note",
    }
    return marker_kinds.get(entry.entry_type)


def _compute_daily_protocols(
    selected_days: list[date],
    readings_by_date: dict[str, list[_ReadingSample]],
    entries_by_date: dict[str, list[LogEntry]],
) -> list[DayProtocol]:
    """Build 24 clinical hourly intervals and log markers for each day."""
    protocols: list[DayProtocol] = []
    for day in selected_days:
        day_key = day.isoformat()
        day_readings = readings_by_date.get(day_key, [])
        values_by_hour: list[list[int]] = [[] for _ in range(24)]
        for reading in day_readings:
            if not reading.is_compression_low:
                values_by_hour[reading.local_minutes // 60].append(reading.sgv)
        intervals: list[IntervalMinMax] = []
        for hour in range(24):
            values = values_by_hour[hour]
            intervals.append(
                IntervalMinMax(
                    hour=hour,
                    time_start=_time_label(hour * 60),
                    time_end=_time_label((hour + 1) % 24 * 60),
                    min_val=min(values) if values else None,
                    max_val=max(values) if values else None,
                )
            )

        marker_entries = [
            (entry, kind)
            for entry in sorted(
                entries_by_date.get(day_key, []), key=lambda entry: _as_utc(entry.created_at)
            )
            if (kind := _marker_kind(entry)) is not None
        ]
        marker_count = len(marker_entries)
        markers = [
            LogMarker(
                timestamp=_display_timestamp(entry.created_at),
                kind=kind,
                value=entry.value,
                unit=entry.unit,
                notes=(
                    entry.notes[: _MAX_LOG_MARKER_NOTE_CHARS - 3] + "..."
                    if entry.notes and len(entry.notes) > _MAX_LOG_MARKER_NOTE_CHARS
                    else entry.notes
                ),
            )
            for entry, kind in marker_entries[:_MAX_LOG_MARKERS_PER_DAY]
        ]
        protocols.append(
            DayProtocol(
                date=day_key,
                weekday=_weekday_de(day),
                intervals=intervals,
                markers=markers,
                marker_count=marker_count,
                markers_truncated=marker_count > len(markers),
            )
        )
    return protocols


# ── Snapshot, meal, daily pattern, and weekly views ──────────────────────


def _compute_snapshot(
    entries: list[LogEntry],
    period_days: int,
    glucose_stats: GlucoseStats,
    low_events: list[LowGlucoseEvent],
    coverage_profile: list[CoveragePoint],
) -> ReportSnapshot:
    """Build compact period totals and low-episode summary."""
    carbs, rapid, basal, total = _entry_totals(entries)
    average_duration = (
        round(sum(event.duration_minutes for event in low_events) / len(low_events), 1)
        if low_events
        else None
    )
    low_event_details = low_events[:_MAX_LOW_EVENT_DETAILS]
    return ReportSnapshot(
        mean_sgv=glucose_stats.mean,
        gmi=glucose_stats.gmi,
        gmi_mmol_mol=glucose_stats.gmi_mmol_mol,
        tir_percent=glucose_stats.tir_percent,
        below_percent=glucose_stats.tir_below,
        above_percent=glucose_stats.tir_above,
        low_events_count=len(low_events),
        low_events_avg_duration_minutes=average_duration,
        data_coverage_percent=glucose_stats.data_coverage_percent,
        carbs_daily_avg=round(carbs / period_days, 1),
        rapid_insulin_daily_avg=round(rapid / period_days, 1),
        basal_insulin_daily_avg=round(basal / period_days, 1),
        total_insulin_daily_avg=round(total / period_days, 1),
        coverage_profile=coverage_profile,
        low_events=low_event_details,
        low_events_truncated=len(low_events) > len(low_event_details),
    )


def _meal_block_entries(entries: list[LogEntry], start_hour: int, end_hour: int) -> list[LogEntry]:
    """Return carbohydrate entries whose local time belongs to one meal block."""
    block_entries: list[LogEntry] = []
    for entry in entries:
        if entry.entry_type != LogEntryType.CARBS or entry.value <= 0:
            continue
        local_timestamp = _to_local(entry.created_at)
        hour = local_timestamp.hour + local_timestamp.minute / 60
        if (start_hour < end_hour and start_hour <= hour < end_hour) or (
            start_hour > end_hour and (hour >= start_hour or hour < end_hour)
        ):
            block_entries.append(entry)
    return block_entries


def _find_nearest_idx(timestamps: list[datetime], target: datetime) -> int | None:
    """Return the index of the timestamp nearest to a target timestamp."""
    if not timestamps:
        return None
    low, high = 0, len(timestamps) - 1
    while low < high:
        middle = (low + high) // 2
        if timestamps[middle] < target:
            low = middle + 1
        else:
            high = middle
    if low == 0:
        return low
    before = abs((timestamps[low - 1] - target).total_seconds())
    after = abs((timestamps[low] - target).total_seconds())
    return low - 1 if before <= after else low


def _compute_meal_profile(
    readings: list[_ReadingSample], entries: list[LogEntry]
) -> list[MealBlock]:
    """Compute meal-relative glucose percentile points for all four meal blocks."""
    import numpy as np

    carb_entries = [
        entry for entry in entries if entry.entry_type == LogEntryType.CARBS and entry.value > 0
    ]
    if not carb_entries:
        return [
            MealBlock(name=name, hours_label=f"{start:02d}:00 - {end:02d}:00", points=[])
            for name, (start, end) in _MEAL_BLOCKS.items()
        ]
    sorted_readings = readings
    reading_timestamps = [reading.timestamp for reading in sorted_readings]
    reading_sgvs = [reading.sgv for reading in sorted_readings]
    offsets = (("-1h", -3600), ("+1h", 3600), ("+2h", 7200), ("+3h", 10800))

    blocks: list[MealBlock] = []
    for name, (start_hour, end_hour) in _MEAL_BLOCKS.items():
        block_entries = _meal_block_entries(carb_entries, start_hour, end_hour)
        hours_label = f"{start_hour:02d}:00 - {end_hour:02d}:00"
        if not block_entries:
            blocks.append(MealBlock(name=name, hours_label=hours_label, points=[]))
            continue

        points: list[MealPoint] = []
        for offset_label, offset_seconds in offsets:
            values: list[float] = []
            # Each block must use only its own meals, never all carbohydrate entries.
            for entry in block_entries:
                target = _as_utc(entry.created_at) + timedelta(seconds=offset_seconds)
                index = _find_nearest_idx(reading_timestamps, target)
                if index is None:
                    continue
                difference = abs((reading_timestamps[index] - target).total_seconds())
                if difference <= 900:
                    values.append(float(reading_sgvs[index]))
            if values:
                p25, p50, p75 = np.percentile(np.array(values), [25, 50, 75])
                points.append(
                    MealPoint(
                        offset_label=offset_label,
                        median_sgv=round(float(p50), 1),
                        p25=round(float(p25), 1),
                        p75=round(float(p75), 1),
                    )
                )
            else:
                points.append(MealPoint(offset_label, None, None, None))
        blocks.append(MealBlock(name=name, hours_label=hours_label, points=points))
    return blocks


def _compute_daily_pattern(
    glucose_percentiles: list[
        tuple[float | None, float | None, float | None, float | None, float | None]
    ],
    entries: list[LogEntry],
    period_days: int,
) -> list[DailyPatternPoint]:
    """Compute duration-weighted AGP values and treatment averages."""
    carbs_buckets: list[list[float]] = [[] for _ in range(_AGP_BUCKETS_PER_DAY)]
    rapid_buckets: list[list[float]] = [[] for _ in range(_AGP_BUCKETS_PER_DAY)]
    basal_buckets: list[list[float]] = [[] for _ in range(_AGP_BUCKETS_PER_DAY)]

    for entry in entries:
        bucket = _bucket_index(_time_of_day_minutes(entry.created_at))
        if entry.entry_type == LogEntryType.CARBS:
            carbs_buckets[bucket].append(_carb_grams(entry))
        elif entry.entry_type == LogEntryType.INSULIN:
            rapid_buckets[bucket].append(entry.value)
        elif entry.entry_type == LogEntryType.BASAL:
            basal_buckets[bucket].append(entry.value)

    points: list[DailyPatternPoint] = []
    for index, percentiles in enumerate(glucose_percentiles):
        p5, p25, p50, p75, p95 = percentiles
        points.append(
            DailyPatternPoint(
                time_label=_time_label(index * _AGP_BUCKET_MINUTES),
                p5=p5,
                p25=p25,
                p50=p50,
                p75=p75,
                p95=p95,
                carbs_avg=round(sum(carbs_buckets[index]) / period_days, 1),
                rapid_insulin_avg=round(sum(rapid_buckets[index]) / period_days, 1),
                basal_insulin_avg=round(sum(basal_buckets[index]) / period_days, 1),
            )
        )
    return points


def _compute_weekly_overview(
    selected_days: list[date],
    readings_by_date: dict[str, list[_ReadingSample]],
    entries_by_date: dict[str, list[LogEntry]],
    events_by_date: dict[str, list[LowGlucoseEvent]],
    span_index: _SpanIndex,
) -> list[WeeklyDay]:
    """Build one weekly overview row for each selected date, including empty days."""
    days: list[WeeklyDay] = []
    for day in selected_days:
        day_key = day.isoformat()
        day_spans = span_index.by_date.get(day_key, [])
        day_readings = readings_by_date.get(day_key, [])
        carbs, rapid, basal, total = _entry_totals(entries_by_date.get(day_key, []))
        days.append(
            WeeklyDay(
                date=day_key,
                weekday=_weekday_de(day),
                avg_sgv=(
                    round(
                        span_index.weighted_sgv_seconds_by_date.get(day_key, 0.0)
                        / span_index.coverage_seconds_by_date[day_key],
                        1,
                    )
                    if day_spans
                    else None
                ),
                carbs_total=carbs,
                rapid_insulin_total=rapid,
                basal_insulin_total=basal,
                total_insulin=total,
                low_events=len(events_by_date.get(day_key, [])),
                reading_count=sum(not reading.is_compression_low for reading in day_readings),
                data_coverage_percent=_daily_coverage_percent(span_index, day),
            )
        )
    return days


# ── Main entry point ──────────────────────────────────────────────────────


def compute_report_data(
    start: date | datetime,
    end: date | datetime,
    readings: list[GlucoseReading],
    entries: list[LogEntry],
    patient_name: str = "",
    predecessor: GlucoseReading | None = None,
    effective_end: datetime | None = None,
) -> ReportData:
    """Compute a complete report for an inclusive Europe/Berlin date range.

    ``start`` and ``end`` are calendar dates. Datetime inputs are converted to
    Europe/Berlin before deriving their date. ``predecessor`` is clinical span
    context only and is never exposed or included in selected reading counts.
    """
    selected_days = _selected_dates(start, end)
    selected_date_keys = {day.isoformat() for day in selected_days}
    start_utc, _ = _day_bounds(selected_days[0])
    _, calendar_end_utc = _day_bounds(selected_days[-1])
    end_utc = min(_as_utc(effective_end), calendar_end_utc) if effective_end else calendar_end_utc
    if end_utc < start_utc:
        raise ValueError("report effective end must not precede its start")
    readings_local, entries_local, clinical_reading_count, readings_by_date, entries_by_date = (
        _collect_local(readings, entries, selected_date_keys, start_utc, end_utc)
    )
    clinical_selected_readings = [
        reading for reading in readings_local if not reading.is_compression_low
    ]
    # Keep compression-low timestamps as span boundaries, but never emit them
    # as clinical spans. This avoids carrying a prior glucose state across a
    # known-invalid observation while retaining the raw trace separately.
    clinical_context_readings = list(readings_local)
    if (
        predecessor is not None
        and predecessor.sgv is not None
        and _as_utc(predecessor.timestamp) < start_utc
    ):
        clinical_context_readings.insert(0, _reading_sample(predecessor))
    observation_spans = _observation_spans(clinical_context_readings, start_utc, end_utc)
    span_index = _build_span_index(observation_spans, start_utc, end_utc)
    agp_percentiles = [_weighted_percentiles(bucket) for bucket in span_index.agp_buckets]
    trace_points_by_date = {
        day_key: _glucose_points(day_readings) for day_key, day_readings in readings_by_date.items()
    }
    report_seconds = (end_utc - start_utc).total_seconds()
    data_coverage_percent = (
        round(span_index.total_coverage_seconds / report_seconds * 100, 1)
        if report_seconds > 0
        else 0.0
    )
    glucose_stats = _compute_glucose_stats(
        clinical_reading_count,
        span_index,
        data_coverage_percent,
    )
    # Context supports observed-time spans only; episodes remain selected-period
    # events. Compression-low readings are retained here as episode boundaries.
    low_events = _compute_low_events(readings_local)
    events_by_date = _events_by_date(low_events)
    coverage_profile = _coverage_profile(span_index, selected_days)
    period_days = len(selected_days)

    return ReportData(
        patient_name=patient_name,
        generated_at=datetime.now(LOCAL_TZ).isoformat(timespec="seconds"),
        timezone=LOCAL_TZ.key,
        period=ReportPeriod(
            start=selected_days[0].isoformat(),
            end=selected_days[-1].isoformat(),
            num_days=period_days,
        ),
        glucose_stats=glucose_stats,
        agp_curve=_compute_agp_curve(agp_percentiles),
        daily_profiles=_compute_daily_profiles(
            selected_days,
            entries_by_date,
            events_by_date,
            span_index,
            trace_points_by_date,
        ),
        monthly_overview=_compute_monthly_overview(
            selected_days,
            readings_by_date,
            entries_by_date,
            events_by_date,
            span_index,
        ),
        daily_protocols=_compute_daily_protocols(
            selected_days,
            readings_by_date,
            entries_by_date,
        ),
        snapshot=_compute_snapshot(
            entries_local,
            period_days,
            glucose_stats,
            low_events,
            coverage_profile,
        ),
        meal_profile=_compute_meal_profile(clinical_selected_readings, entries_local),
        daily_pattern=_compute_daily_pattern(agp_percentiles, entries_local, period_days),
        weekly_overview=_compute_weekly_overview(
            selected_days,
            readings_by_date,
            entries_by_date,
            events_by_date,
            span_index,
        ),
    )
