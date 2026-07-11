"""Tests for prediction feature engineering — plan task 3."""

import math
from datetime import UTC, datetime, timedelta

import pytest

from bgmon_api.models import (
    BasalRateHistory,
    GlobalSettings,
    GlucoseReading,
    LogEntry,
    LogEntryType,
)
from bgmon_api.services.feature_builder import (
    FeatureBuilder,
    FeatureContext,
    InsufficientContextError,
    feature_names,
)


def _make_bg(timestamp: datetime, sgv: int) -> GlucoseReading:
    reading = GlucoseReading()
    reading.timestamp = timestamp
    reading.sgv = sgv
    reading.source = "test"
    return reading


def _make_log(
    created_at: datetime, entry_type: LogEntryType, value: float, unit: str = "g",
) -> LogEntry:
    entry = LogEntry()
    entry.user_id = 1
    entry.entry_type = entry_type
    entry.value = value
    entry.unit = unit
    entry.created_at = created_at
    return entry


def _normal_history_fixture() -> FeatureContext:
    """6 hours of BG history, log entries within 2h window, basal rate set."""
    now = datetime.now(UTC)
    base = now - timedelta(hours=6)

    bg_values = [
        120, 118, 115, 112, 110, 108, 105, 103, 100, 98,
        95, 93, 90, 88, 85, 82, 80, 78, 75, 72,
        70, 80, 95, 110, 125, 140, 155, 170, 180, 175,
        165, 150, 140, 130, 125, 120,
    ]
    bg_readings = [
        _make_bg(base + timedelta(minutes=i * 10), bg_values[i])
        for i in range(len(bg_values))
    ]

    # Log entries within last 2 hours (relative to now)
    log_entries = [
        _make_log(now - timedelta(minutes=90), LogEntryType.CARBS, 30.0, "g"),
        _make_log(now - timedelta(minutes=85), LogEntryType.INSULIN, 3.0, "U"),
        _make_log(now - timedelta(minutes=90), LogEntryType.BASAL, 1.0, "U/h"),
        _make_log(now - timedelta(minutes=30), LogEntryType.CARBS, 20.0, "g"),
        _make_log(now - timedelta(minutes=25), LogEntryType.INSULIN, 2.0, "U"),
    ]

    basal_rate = BasalRateHistory()
    basal_rate.user_id = 1
    basal_rate.rate = 1.0
    basal_rate.unit = "U/h"
    basal_rate.changed_at = base - timedelta(days=1)

    settings = GlobalSettings()
    settings.insulin_action_hours = 4.0
    settings.correction_factor = 50.0

    return FeatureContext(
        glucose_readings=bg_readings,
        log_entries=log_entries,
        basal_rate=basal_rate,
        global_settings=settings,
        reference_time=now,
    )


def _sparse_log_fixture() -> FeatureContext:
    """Minimal: only 3 BG readings, 1 log entry, no basal."""
    now = datetime.now(UTC)
    base = now - timedelta(hours=1)
    bg_readings = [
        _make_bg(base, 120),
        _make_bg(base + timedelta(minutes=15), 130),
        _make_bg(base + timedelta(minutes=30), 118),
    ]
    log_entries = [
        _make_log(base, LogEntryType.CARBS, 15.0, "g"),
    ]
    return FeatureContext(
        glucose_readings=bg_readings,
        log_entries=log_entries,
        basal_rate=None,
        global_settings=None,
        reference_time=now,
    )


def _no_data_fixture() -> FeatureContext:
    return FeatureContext(
        glucose_readings=[],
        log_entries=[],
        basal_rate=None,
        global_settings=None,
        reference_time=datetime.now(UTC),
    )


def _stale_bg_fixture() -> FeatureContext:
    """BG readings >30 min old relative to reference_time."""
    now = datetime.now(UTC)
    base = now - timedelta(hours=12)
    bg_readings = [
        _make_bg(base + timedelta(minutes=i * 10), 100 + i * 2)
        for i in range(6)
    ]
    return FeatureContext(
        glucose_readings=bg_readings,
        log_entries=[],
        basal_rate=None,
        global_settings=None,
        reference_time=now,
    )


# ── no-data / stale tests (failing-first) ─────────────────────────────


class TestInsufficientContext:
    """InsufficientContextError is raised when data is missing or stale."""

    def test_no_data_raises_insufficient_context(self):
        ctx = _no_data_fixture()
        with pytest.raises(InsufficientContextError) as exc_info:
            FeatureBuilder().build_features(ctx)
        assert exc_info.value.reason == "no_glucose_data"

    def test_stale_bg_raises_insufficient_context(self):
        ctx = _stale_bg_fixture()
        with pytest.raises(InsufficientContextError) as exc_info:
            FeatureBuilder().build_features(ctx)
        assert exc_info.value.reason == "stale_glucose_data"

    def test_insufficient_context_is_runtime_error(self):
        assert issubclass(InsufficientContextError, RuntimeError)

    def test_insufficient_context_carries_reason_and_context(self):
        ctx = _no_data_fixture()
        with pytest.raises(InsufficientContextError) as exc_info:
            FeatureBuilder().build_features(ctx)
        assert exc_info.value.reason == "no_glucose_data"
        assert exc_info.value.context is ctx


# ── feature extraction tests ──────────────────────────────────────────


class TestFeatureExtraction:
    """Feature values are computed from history correctly."""

    def test_latest_bg_extracted(self):
        ctx = _normal_history_fixture()
        result = FeatureBuilder().build_features(ctx)
        assert result.latest_bg == 120

    def test_bg_mean_30m_extracted(self):
        ctx = _normal_history_fixture()
        result = FeatureBuilder().build_features(ctx)
        # Last 3 values at -20, -10, 0 min: 130, 125, 120 → mean = 125
        assert result.bg_mean_30m == pytest.approx(125.0)

    def test_bg_mean_120m_extracted(self):
        ctx = _normal_history_fixture()
        result = FeatureBuilder().build_features(ctx)
        # Last 12 values from -110 to 0 min: all should be in 2h window
        assert result.bg_mean_120m > 0

    def test_bg_slope_30m_extracted(self):
        ctx = _normal_history_fixture()
        result = FeatureBuilder().build_features(ctx)
        # Last 3 values: [+10: 130, +20: 125, now: 120] over 20 min
        # slope = (120 - 130) / 20 = -0.5
        assert result.bg_slope_30m_per_min == pytest.approx(-0.5)

    def test_carbs_sum_2h(self):
        ctx = _normal_history_fixture()
        result = FeatureBuilder().build_features(ctx)
        # Entries at now - 90min and now - 30min → both in 2h window
        assert result.carbs_sum_2h == pytest.approx(50.0)

    def test_insulin_sum_2h(self):
        ctx = _normal_history_fixture()
        result = FeatureBuilder().build_features(ctx)
        assert result.insulin_sum_2h == pytest.approx(5.0)

    def test_basal_rate_extracted(self):
        ctx = _normal_history_fixture()
        result = FeatureBuilder().build_features(ctx)
        assert result.basal_rate_u_h == pytest.approx(1.0)

    def test_basal_rate_none_when_missing(self):
        ctx = _sparse_log_fixture()
        result = FeatureBuilder().build_features(ctx)
        assert result.basal_rate_u_h == 0.0

    def test_insulin_action_hours_extracted(self):
        ctx = _normal_history_fixture()
        result = FeatureBuilder().build_features(ctx)
        assert result.insulin_action_hours == 4.0

    def test_correction_factor_extracted(self):
        ctx = _normal_history_fixture()
        result = FeatureBuilder().build_features(ctx)
        assert result.correction_factor == 50.0

    def test_settings_defaults_when_none(self):
        ctx = _sparse_log_fixture()
        result = FeatureBuilder().build_features(ctx)
        assert result.insulin_action_hours == 4.0
        assert result.correction_factor == 50.0


# ── time-of-day features ──────────────────────────────────────────────


class TestTimeOfDayFeatures:
    """Cyclical hour-of-day encoding is deterministic."""

    @staticmethod
    def _build_ctx_for_hour(hour: int) -> FeatureContext:
        ref_time = datetime(2026, 7, 10, hour, 0, 0, tzinfo=UTC)
        bg_readings = [
            _make_bg(ref_time - timedelta(minutes=i * 10), 100 + i)
            for i in range(36)
        ]
        return FeatureContext(
            glucose_readings=bg_readings,
            log_entries=[],
            basal_rate=None,
            global_settings=None,
            reference_time=ref_time,
        )

    def test_hour_sine_at_midnight(self):
        ctx = self._build_ctx_for_hour(0)
        result = FeatureBuilder().build_features(ctx)
        assert result.hour_sin == pytest.approx(0.0, abs=1e-3)

    def test_hour_cosine_at_midnight(self):
        ctx = self._build_ctx_for_hour(0)
        result = FeatureBuilder().build_features(ctx)
        assert result.hour_cos == pytest.approx(1.0, abs=1e-3)

    def test_hour_sine_at_6am(self):
        ctx = self._build_ctx_for_hour(6)
        result = FeatureBuilder().build_features(ctx)
        assert result.hour_sin == pytest.approx(1.0, abs=1e-3)

    def test_hour_cosine_at_6am(self):
        ctx = self._build_ctx_for_hour(6)
        result = FeatureBuilder().build_features(ctx)
        assert result.hour_cos == pytest.approx(0.0, abs=1e-3)


# ── sparse / edge case tests ──────────────────────────────────────────


class TestSparseLogBehavior:
    """Correct handling of minimal history."""

    def test_sparse_log_returns_features_not_exception(self):
        ctx = _sparse_log_fixture()
        result = FeatureBuilder().build_features(ctx)
        assert result.latest_bg == 118
        assert result.carbs_sum_2h == 15.0
        assert result.insulin_sum_2h == 0.0
        assert result.basal_rate_u_h == 0.0

    def test_sparse_log_bg_mean_stable(self):
        """Given: 3 BG readings → Then: bg_mean_30m from last reading in window.

        The 3 readings are at now-60, now-45, now-30. The 30min window is
        [now-30, now], so only the last reading (118) qualifies.
        """
        ctx = _sparse_log_fixture()
        result = FeatureBuilder().build_features(ctx)
        assert result.bg_mean_30m == pytest.approx(118.0)

    def test_sparse_log_slope(self):
        ctx = _sparse_log_fixture()
        result = FeatureBuilder().build_features(ctx)
        # Only 1 point in 30min window → slope = 0
        assert result.bg_slope_30m_per_min == 0.0

    def test_no_log_entries(self):
        now = datetime.now(UTC)
        base = now - timedelta(hours=2)
        ctx = FeatureContext(
            glucose_readings=[
                _make_bg(base + timedelta(minutes=i * 10), 100 + i)
                for i in range(12)
            ],
            log_entries=[],
            basal_rate=None,
            global_settings=None,
            reference_time=now,
        )
        result = FeatureBuilder().build_features(ctx)
        assert result.carbs_sum_2h == 0.0
        assert result.insulin_sum_2h == 0.0


# ── feature vector / matrix tests ─────────────────────────────────────


class TestFeatureVectorShape:
    """Feature vectors are deterministic and correctly shaped."""

    def test_feature_names_are_exhaustive(self):
        names = feature_names()
        expected = {
            "latest_bg",
            "bg_mean_30m",
            "bg_mean_60m",
            "bg_mean_120m",
            "bg_slope_30m_per_min",
            "bg_slope_60m_per_min",
            "carbs_sum_2h",
            "carbs_sum_4h",
            "insulin_sum_2h",
            "insulin_sum_4h",
            "basal_rate_u_h",
            "insulin_action_hours",
            "correction_factor",
            "hour_sin",
            "hour_cos",
        }
        actual = set(names)
        missing = expected - actual
        extra = actual - expected
        assert not missing, f"Missing features: {missing}"
        assert not extra, f"Extra features: {extra}"

    def test_feature_vector_length_is_15(self):
        ctx = _normal_history_fixture()
        result = FeatureBuilder().build_features(ctx)
        vec = result.to_feature_vector()
        assert len(vec) == 15

    def test_feature_vector_is_deterministic(self):
        ctx = _normal_history_fixture()
        v1 = FeatureBuilder().build_features(ctx).to_feature_vector()
        v2 = FeatureBuilder().build_features(ctx).to_feature_vector()
        assert v1 == v2

    def test_feature_matrix_for_horizons(self):
        ctx = _normal_history_fixture()
        builder = FeatureBuilder()
        result = builder.build_features(ctx)
        matrix = result.to_feature_matrix()
        assert len(matrix) == 1
        assert len(matrix[0]) == 15

    def test_multiple_horizons_same_features(self):
        ctx = _normal_history_fixture()
        builder = FeatureBuilder()
        r1 = builder.build_features(ctx, horizon_minutes=60)
        r2 = builder.build_features(ctx, horizon_minutes=120)
        assert r1.to_feature_vector() == r2.to_feature_vector()


# ── numeric precision ─────────────────────────────────────────────────


class TestFeaturePrecision:
    """Feature values are computed with acceptable precision."""

    def test_bg_stats_are_finite(self):
        ctx = _normal_history_fixture()
        result = FeatureBuilder().build_features(ctx)
        assert math.isfinite(result.latest_bg)
        assert math.isfinite(result.bg_mean_30m)
        assert math.isfinite(result.bg_slope_30m_per_min)

    def test_slope_zero_for_flat_line(self):
        now = datetime.now(UTC)
        base = now - timedelta(hours=2)
        ctx = FeatureContext(
            glucose_readings=[
                _make_bg(base + timedelta(minutes=i * 10), 100)
                for i in range(12)
            ],
            log_entries=[],
            basal_rate=None,
            global_settings=None,
            reference_time=now,
        )
        result = FeatureBuilder().build_features(ctx)
        assert result.bg_slope_30m_per_min == pytest.approx(0.0)
        assert result.bg_slope_60m_per_min == pytest.approx(0.0)
