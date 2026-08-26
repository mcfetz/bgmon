from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from time import perf_counter
from zoneinfo import ZoneInfo

from bgmon_api.models import (
    MAX_LOG_ENTRY_VALUE,
    GlucoseReading,
    LogEntry,
    LogEntryType,
    User,
    UserRole,
)
from bgmon_api.services.report_service import compute_report_data


def _reading(
    timestamp: datetime,
    sgv: int,
    *,
    source: str = "test",
    is_compression_low: bool = False,
) -> GlucoseReading:
    return GlucoseReading(
        timestamp=timestamp,
        sgv=sgv,
        trend=None,
        direction=None,
        source=source,
        is_compression_low=is_compression_low,
    )


def _entry(
    timestamp: datetime,
    entry_type: LogEntryType,
    value: float,
    *,
    user_id: int = 1,
    notes: str | None = None,
    unit: str | None = None,
) -> LogEntry:
    return LogEntry(
        user_id=user_id,
        entry_type=entry_type,
        value=value,
        unit=unit if unit is not None else ("g" if entry_type == LogEntryType.CARBS else "U"),
        notes=notes,
        created_at=timestamp,
    )


def _point_by_offset(points, offset_label: str):
    return next(point for point in points if point.offset_label == offset_label)


def test_meal_profile_uses_only_meals_from_its_block_and_keeps_empty_blocks():
    # June is CEST: 06:00 UTC is 08:00 local morning, 16:00 UTC is 18:00 local evening.
    morning_meal = _entry(datetime(2026, 6, 1, 6, 0, tzinfo=UTC), LogEntryType.CARBS, 20)
    evening_meal = _entry(datetime(2026, 6, 1, 16, 0, tzinfo=UTC), LogEntryType.CARBS, 30)
    readings = [
        _reading(datetime(2026, 6, 1, 7, 0, tzinfo=UTC), 110),
        _reading(datetime(2026, 6, 1, 17, 0, tzinfo=UTC), 210),
    ]

    blocks = compute_report_data(
        date(2026, 6, 1),
        date(2026, 6, 1),
        readings,
        [morning_meal, evening_meal],
    ).meal_profile
    by_name = {block.name: block for block in blocks}

    assert [block.name for block in blocks] == ["morning", "midday", "evening", "night"]
    assert _point_by_offset(by_name["morning"].points, "+1h").median_sgv == 110.0
    assert _point_by_offset(by_name["evening"].points, "+1h").median_sgv == 210.0
    assert by_name["midday"].points == []
    assert by_name["night"].points == []

    empty_blocks = compute_report_data(
        date(2026, 6, 1), date(2026, 6, 1), readings, []
    ).meal_profile
    assert [block.name for block in empty_blocks] == ["morning", "midday", "evening", "night"]
    assert all(block.points == [] for block in empty_blocks)


def test_report_adds_gmi_ifcc_and_splits_low_episodes_after_long_gaps():
    report = compute_report_data(
        date(2026, 6, 1),
        date(2026, 6, 1),
        [
            _reading(datetime(2026, 6, 1, 6, 0, tzinfo=UTC), 65),
            _reading(datetime(2026, 6, 1, 6, 10, tzinfo=UTC), 60),
            # The 20-minute gap starts a second low episode.
            _reading(datetime(2026, 6, 1, 6, 30, tzinfo=UTC), 65),
            _reading(datetime(2026, 6, 1, 6, 40, tzinfo=UTC), 120),
        ],
        [],
    )

    assert report.glucose_stats.gmi is not None
    assert report.glucose_stats.gmi_mmol_mol == round((report.glucose_stats.gmi - 2.15) / 0.0915)
    assert report.snapshot.gmi_mmol_mol == report.glucose_stats.gmi_mmol_mol
    assert report.snapshot.low_events_count == 2
    assert report.daily_profiles[0].low_events == 2
    assert report.monthly_overview[0].low_events == 2
    assert report.weekly_overview[0].low_events == 2
    assert report.snapshot.low_events_truncated is False


def test_report_normalizes_logged_ke_to_carbohydrate_grams():
    start = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
    report = compute_report_data(
        date(2026, 1, 1),
        date(2026, 1, 1),
        [_reading(start, 120), _reading(start + timedelta(minutes=5), 125)],
        [
            _entry(start, LogEntryType.CARBS, 3, unit="KE"),
            _entry(start + timedelta(hours=1), LogEntryType.CARBS, 15, unit="g"),
        ],
    )

    assert report.daily_profiles[0].carbs_total == 45.0
    assert report.monthly_overview[0].carbs_total == 45.0
    assert report.weekly_overview[0].carbs_total == 45.0
    assert report.snapshot.carbs_daily_avg == 45.0


def test_report_uses_berlin_dates_and_spines_all_daily_views():
    # 23:30 UTC on 1 January is 00:30 on 2 January in Europe/Berlin.
    reading = _reading(datetime(2026, 1, 1, 23, 30, tzinfo=UTC), 120)
    rapid = _entry(datetime(2026, 1, 1, 23, 45, tzinfo=UTC), LogEntryType.INSULIN, 2.5)
    basal = _entry(datetime(2026, 1, 1, 23, 50, tzinfo=UTC), LogEntryType.BASAL, 10)
    note = _entry(datetime(2026, 1, 1, 23, 55, tzinfo=UTC), LogEntryType.NOTE, 0, notes="test")

    report = compute_report_data(
        date(2026, 1, 1), date(2026, 1, 3), [reading], [rapid, basal, note]
    )

    expected_dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert report.period.start == expected_dates[0]
    assert report.period.end == expected_dates[-1]
    assert report.period.num_days == 3
    assert [profile.date for profile in report.daily_profiles] == expected_dates
    assert [overview.date for overview in report.monthly_overview] == expected_dates
    assert [protocol.date for protocol in report.daily_protocols] == expected_dates
    assert [overview.date for overview in report.weekly_overview] == expected_dates
    assert report.daily_profiles[0].readings == []
    assert report.daily_profiles[1].readings[0].timestamp == "2026-01-02T00:30:00+01:00"
    assert report.daily_profiles[1].rapid_insulin_total == 2.5
    assert report.daily_profiles[1].basal_insulin_total == 10.0
    assert report.daily_profiles[1].total_insulin == 12.5
    assert report.daily_profiles[2].avg is None
    assert len(report.daily_protocols[1].intervals) == 24
    assert [marker.kind for marker in report.daily_protocols[1].markers] == [
        "rapid_insulin",
        "basal",
        "note",
    ]
    assert len(report.snapshot.coverage_profile) == 12
    assert "sensor_active_percent" not in asdict(report)["glucose_stats"]
    assert "avg_scans_per_day" not in asdict(report)["snapshot"]


def test_daily_protocol_caps_markers_and_long_notes():
    timestamp = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
    entries = [
        _entry(
            timestamp + timedelta(minutes=index),
            LogEntryType.NOTE,
            0,
            notes="x" * 300,
        )
        for index in range(55)
    ]
    report = compute_report_data(
        date(2026, 1, 1),
        date(2026, 1, 1),
        [_reading(timestamp, 120), _reading(timestamp + timedelta(minutes=5), 125)],
        entries,
    )

    protocol = report.daily_protocols[0]
    assert protocol.marker_count == 55
    assert protocol.markers_truncated is True
    assert len(protocol.markers) == 50
    assert all(marker.notes is not None and len(marker.notes) == 240 for marker in protocol.markers)
    assert all(marker.notes.endswith("...") for marker in protocol.markers)


def test_report_skips_non_finite_legacy_log_values():
    timestamp = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
    report = compute_report_data(
        date(2026, 1, 1),
        date(2026, 1, 1),
        [_reading(timestamp, 120), _reading(timestamp + timedelta(minutes=5), 125)],
        [
            _entry(timestamp, LogEntryType.CARBS, 20),
            _entry(timestamp, LogEntryType.INSULIN, float("nan")),
            _entry(timestamp, LogEntryType.BASAL, float("inf")),
            _entry(timestamp, LogEntryType.NOTE, float("nan"), notes="ignored"),
            _entry(timestamp, LogEntryType.CARBS, MAX_LOG_ENTRY_VALUE + 1, unit="KE"),
        ],
    )

    profile = report.daily_profiles[0]
    assert profile.carbs_total == 20.0
    assert profile.rapid_insulin_total == 0.0
    assert profile.basal_insulin_total == 0.0
    assert profile.total_insulin == 0.0
    assert report.daily_protocols[0].marker_count == 1
    assert json.dumps(asdict(report), allow_nan=False)


def test_duration_weighting_limits_short_high_sample_and_splits_agp_buckets():
    # January is CET. The final five-minute span starts at 08:26 local and
    # crosses the 08:30 AGP boundary, so it must contribute to both buckets.
    report = compute_report_data(
        date(2026, 1, 1),
        date(2026, 1, 1),
        [
            _reading(datetime(2026, 1, 1, 7, 0, tzinfo=UTC), 100),
            _reading(datetime(2026, 1, 1, 7, 5, tzinfo=UTC), 300),
            # This next observation limits the high value to one observed minute.
            _reading(datetime(2026, 1, 1, 7, 6, tzinfo=UTC), 100),
            _reading(datetime(2026, 1, 1, 7, 11, tzinfo=UTC), 100),
            _reading(datetime(2026, 1, 1, 7, 16, tzinfo=UTC), 100),
            _reading(datetime(2026, 1, 1, 7, 26, tzinfo=UTC), 100),
        ],
        [],
    )

    stats = report.glucose_stats
    assert stats.mean == 107.7
    assert stats.gmi == 5.9
    assert stats.std_dev == 38.5
    assert stats.cv_percent == 35.7
    assert stats.tir_percent == 96.2
    assert stats.tir_above == 3.8
    assert stats.time_70_180_percent == 96.2
    assert stats.time_above_250_percent == 3.8
    assert report.daily_profiles[0].avg == 107.7

    agp_by_label = {point.time_label: point for point in report.agp_curve}
    assert agp_by_label["08:00"].p50 == 100.0
    assert agp_by_label["08:00"].p95 == 100.0
    assert agp_by_label["08:30"].p50 == 100.0
    pattern_by_label = {point.time_label: point for point in report.daily_pattern}
    assert pattern_by_label["08:00"].p95 == 100.0
    assert pattern_by_label["08:30"].p50 == 100.0


def test_duration_weighting_excludes_long_polling_gaps_from_stats_and_coverage():
    report = compute_report_data(
        date(2026, 1, 1),
        date(2026, 1, 1),
        [
            _reading(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), 100),
            _reading(datetime(2026, 1, 1, 0, 5, tzinfo=UTC), 100),
            _reading(datetime(2026, 1, 1, 0, 10, tzinfo=UTC), 300),
            # The four-hour polling gap must not treat 300 mg/dL as continuous.
            _reading(datetime(2026, 1, 1, 4, 10, tzinfo=UTC), 100),
            _reading(datetime(2026, 1, 1, 4, 15, tzinfo=UTC), 100),
        ],
        [],
    )

    assert report.glucose_stats.mean == 140.0
    assert report.glucose_stats.gmi == 6.7
    assert report.glucose_stats.tir_percent == 80.0
    assert report.glucose_stats.tir_above == 20.0
    assert report.glucose_stats.data_coverage_percent == 1.7
    assert report.daily_profiles[0].avg == 140.0


def test_predecessor_covers_berlin_period_start_but_is_not_exposed_or_counted():
    # Berlin 2026-01-10 begins at 2026-01-09T23:00Z. The predecessor covers
    # the first five selected minutes but must not appear as a selected trace.
    predecessor = _reading(datetime(2026, 1, 9, 22, 59, tzinfo=UTC), 120)
    selected = _reading(datetime(2026, 1, 9, 23, 4, tzinfo=UTC), 180)

    report = compute_report_data(
        date(2026, 1, 10),
        date(2026, 1, 10),
        [selected],
        [],
        predecessor=predecessor,
    )

    assert report.glucose_stats.readings == 1
    assert report.glucose_stats.min_val == 120
    assert report.glucose_stats.max_val == 180
    assert report.glucose_stats.mean == 153.3
    assert [point.sgv for point in report.daily_profiles[0].readings] == [180]
    assert report.daily_profiles[0].data_coverage_percent == 0.6


def test_predecessor_respects_berlin_dst_boundary():
    # Berlin's 2026 spring DST day begins at 23:00Z on 28 March.
    predecessor = _reading(datetime(2026, 3, 28, 22, 59, tzinfo=UTC), 100)
    selected = _reading(datetime(2026, 3, 28, 23, 4, tzinfo=UTC), 200)

    report = compute_report_data(
        date(2026, 3, 29),
        date(2026, 3, 29),
        [selected],
        [],
        predecessor=predecessor,
    )

    assert report.glucose_stats.readings == 1
    assert report.glucose_stats.mean == 155.6
    assert report.daily_profiles[0].date == "2026-03-29"
    assert [point.timestamp for point in report.daily_profiles[0].readings] == [
        "2026-03-29T00:04:00+01:00"
    ]


def test_compression_lows_remain_in_raw_trace_but_not_clinical_aggregates():
    readings = [
        _reading(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), 100),
        _reading(
            datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
            45,
            is_compression_low=True,
        ),
        _reading(datetime(2026, 1, 1, 0, 10, tzinfo=UTC), 100),
    ]

    report = compute_report_data(date(2026, 1, 1), date(2026, 1, 1), readings, [])

    assert report.glucose_stats.readings == 2
    assert report.glucose_stats.mean == 100.0
    assert report.glucose_stats.tir_percent == 100.0
    assert report.glucose_stats.time_below_54_percent == 0.0
    assert report.snapshot.low_events_count == 0
    raw_points = report.daily_profiles[0].readings
    assert [point.sgv for point in raw_points] == [100, 45, 100]
    assert [point.is_compression_low for point in raw_points] == [False, True, False]
    assert report.daily_protocols[0].intervals[1].min_val == 100
    assert report.daily_protocols[0].intervals[1].max_val == 100
    assert report.monthly_overview[0].reading_count == 2
    assert report.weekly_overview[0].reading_count == 2
    serialized = asdict(report)
    assert "readings" not in serialized["daily_protocols"][0]
    assert "glucose_points" not in serialized["weekly_overview"][0]


def test_compression_low_splits_an_existing_low_episode():
    readings = [
        _reading(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), 60),
        _reading(
            datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
            45,
            is_compression_low=True,
        ),
        _reading(datetime(2026, 1, 1, 0, 10, tzinfo=UTC), 60),
        _reading(datetime(2026, 1, 1, 0, 15, tzinfo=UTC), 100),
    ]

    report = compute_report_data(date(2026, 1, 1), date(2026, 1, 1), readings, [])

    assert report.snapshot.low_events_count == 2
    assert [event.sgv for event in report.snapshot.low_events] == [60, 60]


def test_effective_end_limits_current_day_metrics_without_removing_date_spine():
    effective_end = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    readings = [
        _reading(datetime(2026, 1, 1, 11, 55, tzinfo=UTC), 100),
        _reading(datetime(2026, 1, 1, 12, 5, tzinfo=UTC), 300),
    ]

    report = compute_report_data(
        date(2026, 1, 1),
        date(2026, 1, 1),
        readings,
        [],
        effective_end=effective_end,
    )

    assert report.period.num_days == 1
    assert report.glucose_stats.readings == 1
    assert report.glucose_stats.mean == 100.0
    assert report.daily_profiles[0].data_coverage_percent == 0.6
    assert [point.sgv for point in report.daily_profiles[0].readings] == [100]


def test_mixed_cadence_is_inferred_per_local_day_and_source():
    # Day one uses five-minute history; day two uses one-minute live updates.
    # A global median would incorrectly turn day one's final sample into 1 min.
    readings = [
        _reading(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), 100, source="history"),
        _reading(datetime(2026, 1, 1, 0, 5, tzinfo=UTC), 100, source="history"),
        _reading(datetime(2026, 1, 1, 0, 10, tzinfo=UTC), 100, source="history"),
        _reading(datetime(2026, 1, 2, 0, 0, tzinfo=UTC), 100, source="live"),
        _reading(datetime(2026, 1, 2, 0, 1, tzinfo=UTC), 100, source="live"),
        _reading(datetime(2026, 1, 2, 0, 2, tzinfo=UTC), 100, source="live"),
    ]

    report = compute_report_data(date(2026, 1, 1), date(2026, 1, 2), readings, [])

    assert report.daily_profiles[0].data_coverage_percent == 1.0
    assert report.daily_profiles[1].data_coverage_percent == 0.2


def test_same_source_same_day_cadence_regimes_keep_historical_and_live_coverage():
    readings = [
        _reading(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), 100, source="librelinkup"),
        _reading(datetime(2026, 1, 1, 0, 15, tzinfo=UTC), 100, source="librelinkup"),
        _reading(datetime(2026, 1, 1, 0, 30, tzinfo=UTC), 100, source="librelinkup"),
        _reading(datetime(2026, 1, 1, 0, 31, tzinfo=UTC), 100, source="librelinkup"),
        _reading(datetime(2026, 1, 1, 0, 32, tzinfo=UTC), 100, source="librelinkup"),
        _reading(datetime(2026, 1, 1, 0, 33, tzinfo=UTC), 100, source="librelinkup"),
    ]

    report = compute_report_data(date(2026, 1, 1), date(2026, 1, 1), readings, [])

    # 15 + 15 historical minutes, then four one-minute live spans = 34 min.
    assert report.daily_profiles[0].data_coverage_percent == 2.4


def test_one_off_same_source_cadence_jitter_does_not_create_a_regime():
    readings = [
        _reading(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), 100, source="librelinkup"),
        _reading(datetime(2026, 1, 1, 0, 5, tzinfo=UTC), 100, source="librelinkup"),
        _reading(datetime(2026, 1, 1, 0, 20, tzinfo=UTC), 100, source="librelinkup"),
        _reading(datetime(2026, 1, 1, 0, 25, tzinfo=UTC), 100, source="librelinkup"),
        _reading(datetime(2026, 1, 1, 0, 30, tzinfo=UTC), 100, source="librelinkup"),
    ]

    report = compute_report_data(date(2026, 1, 1), date(2026, 1, 1), readings, [])

    # The isolated 15-minute interval remains bounded by the normal 5-minute
    # regime rather than becoming a singleton 15-minute coverage interval.
    assert report.daily_profiles[0].data_coverage_percent == 1.7


def test_exact_twofold_same_source_change_requires_a_sustained_next_interval():
    readings = [
        _reading(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), 100, source="librelinkup"),
        _reading(datetime(2026, 1, 1, 0, 5, tzinfo=UTC), 100, source="librelinkup"),
        _reading(datetime(2026, 1, 1, 0, 10, tzinfo=UTC), 100, source="librelinkup"),
        _reading(datetime(2026, 1, 1, 0, 20, tzinfo=UTC), 100, source="librelinkup"),
        _reading(datetime(2026, 1, 1, 0, 30, tzinfo=UTC), 100, source="librelinkup"),
        _reading(datetime(2026, 1, 1, 0, 40, tzinfo=UTC), 100, source="librelinkup"),
    ]

    report = compute_report_data(date(2026, 1, 1), date(2026, 1, 1), readings, [])

    # 2x cadence is accepted only after the following 10-minute interval confirms it.
    assert report.daily_profiles[0].data_coverage_percent == 3.5


def test_pre_gap_cadence_never_borrows_a_later_same_source_live_regime():
    readings = [
        _reading(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), 100, source="librelinkup"),
        _reading(datetime(2026, 1, 1, 0, 5, tzinfo=UTC), 100, source="librelinkup"),
        _reading(datetime(2026, 1, 1, 0, 10, tzinfo=UTC), 100, source="librelinkup"),
        # Four-hour outage. The preceding 100 must retain the historical 5m cadence.
        _reading(datetime(2026, 1, 1, 4, 10, tzinfo=UTC), 300, source="librelinkup"),
        _reading(datetime(2026, 1, 1, 4, 11, tzinfo=UTC), 300, source="librelinkup"),
        _reading(datetime(2026, 1, 1, 4, 12, tzinfo=UTC), 300, source="librelinkup"),
    ]

    report = compute_report_data(date(2026, 1, 1), date(2026, 1, 1), readings, [])

    # Three historical 5m spans plus three live 1m spans: 18 observed minutes.
    assert report.glucose_stats.mean == 133.3
    assert report.glucose_stats.tir_percent == 83.3
    assert report.glucose_stats.tir_above == 16.7
    assert report.daily_profiles[0].data_coverage_percent == 1.2


def test_dense_trace_keeps_non_extreme_compression_low_marker():
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    readings = [
        _reading(start + timedelta(seconds=index * 30), 100 if index % 2 else 102)
        for index in range(301)
    ]
    marker_timestamp = start + timedelta(minutes=1, seconds=15)
    readings.append(_reading(marker_timestamp, 101, is_compression_low=True))

    report = compute_report_data(date(2026, 1, 1), date(2026, 1, 1), readings, [])

    marker = next(
        point
        for point in report.daily_profiles[0].readings
        if point.timestamp == "2026-01-01T01:01:15+01:00" and point.is_compression_low
    )
    assert marker.sgv == 101
    assert len(report.daily_profiles[0].readings) < len(readings)


def test_trace_downsampling_excludes_compression_values_from_valid_extrema():
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    readings = [
        _reading(start + timedelta(seconds=index * 30), 100 if index % 2 else 120)
        for index in range(301)
    ]
    readings.append(_reading(start + timedelta(minutes=1, seconds=15), 45, is_compression_low=True))

    report = compute_report_data(date(2026, 1, 1), date(2026, 1, 1), readings, [])

    first_bucket = [
        point
        for point in report.daily_profiles[0].readings
        if point.timestamp.startswith("2026-01-01T01:0")
    ]
    assert any(point.sgv == 100 and not point.is_compression_low for point in first_bucket)
    assert any(point.sgv == 120 and not point.is_compression_low for point in first_bucket)
    assert any(point.sgv == 45 and point.is_compression_low for point in first_bucket)


def test_dense_all_compression_trace_keeps_one_marker_per_trace_bucket():
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    readings = [
        _reading(
            start + timedelta(seconds=index * 30),
            45 + index % 8,
            is_compression_low=True,
        )
        for index in range(301)
    ]

    report = compute_report_data(date(2026, 1, 1), date(2026, 1, 1), readings, [])

    raw_points = report.daily_profiles[0].readings
    assert raw_points
    assert all(point.is_compression_low for point in raw_points)
    assert len(raw_points) <= 150


def test_dense_mixed_trace_caps_combined_valid_and_compression_points():
    # Midnight in Berlin on 1 January is 23:00 UTC on the previous day.
    start = datetime(2025, 12, 31, 23, 0, tzinfo=UTC)
    readings = []
    for bucket in range(144):
        timestamp = start + timedelta(minutes=bucket * 10)
        readings.extend(
            [
                _reading(timestamp, 100),
                _reading(timestamp + timedelta(minutes=1), 200),
                _reading(timestamp + timedelta(minutes=2), 45, is_compression_low=True),
            ]
        )

    report = compute_report_data(date(2026, 1, 1), date(2026, 1, 1), readings, [])

    raw_points = report.daily_profiles[0].readings
    assert len(raw_points) == 300
    assert sum(point.is_compression_low for point in raw_points) == 144
    assert any(point.sgv == 100 and not point.is_compression_low for point in raw_points)
    assert any(point.sgv == 200 and not point.is_compression_low for point in raw_points)


def test_snapshot_caps_low_event_details_but_preserves_full_aggregate():
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    readings = []
    for index in range(105):
        event_start = start + timedelta(minutes=index * 20)
        readings.extend(
            [
                _reading(event_start, 60),
                _reading(event_start + timedelta(minutes=5), 100),
            ]
        )

    report = compute_report_data(date(2026, 1, 1), date(2026, 1, 2), readings, [])

    assert report.snapshot.low_events_count == 105
    assert len(report.snapshot.low_events) == 100
    assert report.snapshot.low_events_truncated is True
    assert report.snapshot.low_events[0].time == "01:00"
    assert report.snapshot.low_events[-1].time == "10:00"


def test_fallback_low_events_include_distinct_offset_timestamps():
    readings = [
        _reading(datetime(2026, 10, 25, 0, 30, tzinfo=UTC), 60),
        _reading(datetime(2026, 10, 25, 0, 35, tzinfo=UTC), 100),
        _reading(datetime(2026, 10, 25, 1, 30, tzinfo=UTC), 60),
        _reading(datetime(2026, 10, 25, 1, 35, tzinfo=UTC), 100),
    ]

    report = compute_report_data(date(2026, 10, 25), date(2026, 10, 25), readings, [])

    events = report.snapshot.low_events
    assert [event.time for event in events] == ["02:30", "02:30"]
    assert [event.timestamp for event in events] == [
        "2026-10-25T02:30:00+02:00",
        "2026-10-25T02:30:00+01:00",
    ]


def test_fallback_trace_buckets_keep_both_02xx_folds_and_cap_at_300_points():
    fallback_day_start = datetime(2026, 10, 24, 22, 0, tzinfo=UTC)
    readings = [
        _reading(
            fallback_day_start + timedelta(minutes=offset),
            50 if offset == 125 else 250 if offset == 185 else 120,
        )
        for offset in range(0, 1500, 5)
    ]
    readings.append(_reading(fallback_day_start + timedelta(minutes=1), 120))

    report = compute_report_data(date(2026, 10, 25), date(2026, 10, 25), readings, [])

    raw_points = report.daily_profiles[0].readings
    timestamps = {point.timestamp: point.sgv for point in raw_points}
    assert len(raw_points) <= 300
    assert timestamps["2026-10-25T02:05:00+02:00"] == 50
    assert timestamps["2026-10-25T02:05:00+01:00"] == 250
    assert [point.timestamp for point in raw_points] == sorted(
        (point.timestamp for point in raw_points),
        key=lambda timestamp: datetime.fromisoformat(timestamp).astimezone(UTC),
    )


def test_ninety_day_minute_data_is_bounded_and_trace_downsampled():
    start = date(2026, 1, 1)
    total_minutes = 90 * 24 * 60
    first_timestamp = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    readings = [
        _reading(
            first_timestamp + timedelta(minutes=offset),
            70 + offset % 170,
            source="synthetic",
        )
        for offset in range(total_minutes)
    ]

    started = perf_counter()
    report = compute_report_data(start, start + timedelta(days=89), readings, [])
    elapsed = perf_counter() - started

    # The prior repeated global scans took roughly a minute. Keep this generous
    # enough for shared CI hosts while still catching an O(n^2) regression.
    assert elapsed < 8.0
    assert len(report.daily_profiles) == 90
    assert all(len(profile.readings) <= 300 for profile in report.daily_profiles)
    serialized = asdict(report)
    assert all("readings" not in protocol for protocol in serialized["daily_protocols"])
    assert all("glucose_points" not in day for day in serialized["weekly_overview"])
    assert sum(len(profile["readings"]) for profile in serialized["daily_profiles"]) <= 90 * 300


def test_report_endpoint_scopes_logs_to_patient_and_uses_berlin_half_open_bounds(
    client, db_session, patient_user, observer_user, auth_headers
):
    # 10 January 2026 in Berlin is [2026-01-09T23:00Z, 2026-01-10T23:00Z).
    start = datetime(2026, 1, 9, 23, 0, tzinfo=UTC)
    end_exclusive = datetime(2026, 1, 10, 23, 0, tzinfo=UTC)
    assert patient_user is not None
    patient = db_session.query(User).filter_by(email="patient@example.com").one()
    observer = db_session.query(User).filter_by(email="observer@example.com").one()
    patient_id = patient.id
    observer_id = observer.id
    patient_name = patient.display_name
    db_session.add_all(
        [
            _reading(start, 120),
            _reading(end_exclusive, 180),
            _entry(start, LogEntryType.CARBS, 20, user_id=patient_id),
            _entry(
                datetime(2026, 1, 10, 12, 0, tzinfo=UTC),
                LogEntryType.CARBS,
                99,
                user_id=observer_id,
            ),
            _entry(end_exclusive, LogEntryType.INSULIN, 8, user_id=patient_id),
        ]
    )
    db_session.commit()

    response = client.get(
        "/api/report?start=2026-01-10&end=2026-01-10",
        headers=auth_headers(observer_user),
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.get_json()
    day = payload["daily_profiles"][0]
    assert payload["patient_name"] == patient_name
    assert payload["period"] == {"start": "2026-01-10", "end": "2026-01-10", "num_days": 1}
    assert [point["sgv"] for point in day["readings"]] == [120]
    assert day["readings"][0]["timestamp"] == "2026-01-10T00:00:00+01:00"
    assert day["carbs_total"] == 20.0
    assert day["rapid_insulin_total"] == 0.0


def test_report_endpoint_returns_404_when_no_patient(client, observer_user, auth_headers):
    response = client.get("/api/report", headers=auth_headers(observer_user))

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.get_json() == {"error": "no_patient"}


def test_report_endpoint_rejects_deactivated_session_user(client, inactive_user, auth_headers):
    response = client.get("/api/report", headers=auth_headers(inactive_user))

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.get_json() == {"error": "account deactivated"}


def test_report_endpoint_rejects_earliest_berlin_date_without_server_error(
    client, patient_user, auth_headers
):
    response = client.get(
        "/api/report?start=0001-01-01&end=0001-01-01",
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.get_json() == {"error": "invalid_date_range"}


def test_report_endpoint_returns_conflict_when_multiple_patients(
    client, db_session, patient_user, observer_user, auth_headers
):
    additional_patient = User(
        email="second-patient@example.com",
        display_name="Second Patient",
        role=UserRole.PATIENT,
    )
    additional_patient.set_password("test_password")
    db_session.add(additional_patient)
    db_session.commit()

    response = client.get("/api/report", headers=auth_headers(observer_user))

    assert patient_user is not None
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.get_json() == {
        "error": "multiple_patients",
        "message": "Report requires one patient",
    }


def test_report_endpoint_includes_predecessor_state_without_serializing_it(
    client, db_session, patient_user, auth_headers
):
    predecessor = _reading(datetime(2026, 1, 9, 22, 59, tzinfo=UTC), 120)
    selected = _reading(datetime(2026, 1, 9, 23, 4, tzinfo=UTC), 180)
    db_session.add_all([predecessor, selected])
    db_session.commit()

    response = client.get(
        "/api/report?start=2026-01-10&end=2026-01-10",
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.get_json()
    assert payload["glucose_stats"]["readings"] == 1
    assert payload["glucose_stats"]["mean"] == 153.3
    assert [point["sgv"] for point in payload["daily_profiles"][0]["readings"]] == [180]


def test_report_endpoint_rejects_future_and_date_max(client, patient_user, auth_headers):
    future = (datetime.now(ZoneInfo("Europe/Berlin")).date() + timedelta(days=1)).isoformat()
    future_response = client.get(
        f"/api/report?start={future}&end={future}",
        headers=auth_headers(patient_user),
    )
    date_max_response = client.get(
        "/api/report?start=9999-12-31&end=9999-12-31",
        headers=auth_headers(patient_user),
    )

    assert future_response.status_code == HTTPStatus.BAD_REQUEST
    assert future_response.get_json() == {"error": "future_date_not_allowed"}
    assert date_max_response.status_code == HTTPStatus.BAD_REQUEST
    assert date_max_response.get_json() == {"error": "future_date_not_allowed"}


def test_report_endpoint_rejects_data_above_its_safe_input_limit(
    client, db_session, patient_user, auth_headers, monkeypatch
):
    from bgmon_api.routes import report as report_route

    start = datetime(2026, 1, 9, 23, 0, tzinfo=UTC)
    db_session.add_all([_reading(start, 120), _reading(start + timedelta(minutes=1), 125)])
    db_session.commit()
    monkeypatch.setattr(report_route, "MAX_REPORT_READINGS", 1)

    response = client.get(
        "/api/report?start=2026-01-10&end=2026-01-10",
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.get_json() == {"error": "report_data_limit_exceeded"}


def test_report_endpoint_rate_limits_each_authenticated_user_separately(
    client, patient_user, observer_user, auth_headers
):
    for _ in range(10):
        response = client.get("/api/report", headers=auth_headers(patient_user))
        assert response.status_code == HTTPStatus.OK

    other_user_response = client.get("/api/report", headers=auth_headers(observer_user))
    limited_response = client.get("/api/report", headers=auth_headers(patient_user))

    assert other_user_response.status_code == HTTPStatus.OK
    assert limited_response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert limited_response.is_json
    assert limited_response.get_json() == {"error": "rate_limit_exceeded"}
