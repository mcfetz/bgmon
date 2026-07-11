"""Feature engineering for BG prediction v1.

Builds tabular features from GlucoseReading, LogEntry, BasalRateHistory,
GlobalSettings, and time-of-day signals for a forecast target horizon.

The module uses deterministic window-based aggregation. It never touches the
database directly — callers pass in-memory model instances.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bgmon_api.models import (
        BasalRateHistory,
        GlobalSettings,
        GlucoseReading,
        LogEntry,
    )

# ── error types ────────────────────────────────────────────────────────


class InsufficientContextError(RuntimeError):
    """Raised when build_features() cannot produce a feature vector.

    Callers should catch this and return a controlled unavailable payload
    rather than propagating the exception to the HTTP layer.
    """

    def __init__(self, reason: str, context: FeatureContext) -> None:
        super().__init__(reason)
        self.reason: str = reason
        self.context: FeatureContext = context


# ── data classes ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FeatureContext:
    """Immutable snapshot of all inputs needed to build a feature vector."""

    glucose_readings: list[GlucoseReading]
    log_entries: list[LogEntry]
    basal_rate: BasalRateHistory | None
    global_settings: GlobalSettings | None
    reference_time: datetime

    def __post_init__(self) -> None:
        """Attach UTC timezone to naive reference_time."""
        if self.reference_time.tzinfo is None:
            object.__setattr__(
                self, "reference_time", self.reference_time.replace(tzinfo=UTC)
            )


@dataclass(frozen=True, slots=True)
class FeatureMatrix:
    """Tabular feature matrix and aligned target column (if targets provided)."""

    features: list[list[float]] = field(default_factory=list)
    feature_names: list[str] = field(default_factory=list)
    target_sgv: list[float | None] = field(default_factory=list)


_FEATURE_NAMES: tuple[str, ...] = (
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
)


def feature_names() -> list[str]:
    """Return ordered canonical feature names."""
    return list(_FEATURE_NAMES)


@dataclass(frozen=True, slots=True)
class _FeatureRow:
    """Single-row decomposed feature values.

    Use .to_feature_vector() or .to_feature_matrix() to get the ordered
    float list guaranteed to match feature_names() order.
    """

    latest_bg: float
    bg_mean_30m: float
    bg_mean_60m: float
    bg_mean_120m: float
    bg_slope_30m_per_min: float
    bg_slope_60m_per_min: float
    carbs_sum_2h: float
    carbs_sum_4h: float
    insulin_sum_2h: float
    insulin_sum_4h: float
    basal_rate_u_h: float
    insulin_action_hours: float
    correction_factor: float
    hour_sin: float
    hour_cos: float

    def to_feature_vector(self) -> list[float]:
        """Return ordered float list matching feature_names() order."""
        return [
            self.latest_bg,
            self.bg_mean_30m,
            self.bg_mean_60m,
            self.bg_mean_120m,
            self.bg_slope_30m_per_min,
            self.bg_slope_60m_per_min,
            self.carbs_sum_2h,
            self.carbs_sum_4h,
            self.insulin_sum_2h,
            self.insulin_sum_4h,
            self.basal_rate_u_h,
            self.insulin_action_hours,
            self.correction_factor,
            self.hour_sin,
            self.hour_cos,
        ]

    def to_feature_matrix(self) -> list[list[float]]:
        """Return matrix form (single row for single-sample use)."""
        return [self.to_feature_vector()]


# ── builder ────────────────────────────────────────────────────────────

class FeatureBuilder:
    """Build feature vectors from glucose and treatment history context.

    Usage::

        ctx = FeatureContext(
            glucose_readings=bg_list,
            log_entries=log_list,
            basal_rate=basal,
            global_settings=settings,
            reference_time=datetime.now(UTC),
        )
        try:
            features = FeatureBuilder().build_features(ctx)
            vec = features.to_feature_vector()
        except InsufficientContextError as e:
            # Return controlled unavailable payload
            ...
    """

    # Minimum number of BG readings required
    _MIN_BG_COUNT: int = 2

    # Max age of the most recent BG reading (seconds) before declaring stale
    _MAX_BG_AGE_S: int = 1800  # 30 minutes

    # Look-back windows for feature aggregation
    _WINDOW_30M: timedelta = timedelta(minutes=30)
    _WINDOW_60M: timedelta = timedelta(minutes=60)
    _WINDOW_2H: timedelta = timedelta(hours=2)
    _WINDOW_4H: timedelta = timedelta(hours=4)
    _WINDOW_120M: timedelta = timedelta(hours=2)

    # ── public API ──────────────────────────────────────────────────

    def build_features(
        self,
        context: FeatureContext,
        *,
        horizon_minutes: int | None = None,  # noqa: ARG002 — v1 uses shared features
    ) -> _FeatureRow:
        """Build a single feature row from the given context.

        *horizon_minutes* is accepted for call-site compatibility but has no
        effect on the feature values in v1 (same features for all horizons).
        """
        self._validate_context(context)

        bg_values, bg_timestamps = self._extract_bg_series(context)
        ref_time = context.reference_time

        kwargs: dict[str, float] = {
            "latest_bg": bg_values[-1],
            "bg_mean_30m": self._mean_in_window(
                bg_values, bg_timestamps, ref_time, self._WINDOW_30M
            ),
            "bg_mean_60m": self._mean_in_window(
                bg_values, bg_timestamps, ref_time, self._WINDOW_60M
            ),
            "bg_mean_120m": self._mean_in_window(
                bg_values, bg_timestamps, ref_time, self._WINDOW_120M
            ),
            "bg_slope_30m_per_min": self._slope_in_window(
                bg_values, bg_timestamps, ref_time, self._WINDOW_30M
            ),
            "bg_slope_60m_per_min": self._slope_in_window(
                bg_values, bg_timestamps, ref_time, self._WINDOW_60M
            ),
            "carbs_sum_2h": self._log_sum_in_window(
                context.log_entries, "carbs", ref_time, self._WINDOW_2H
            ),
            "carbs_sum_4h": self._log_sum_in_window(
                context.log_entries, "carbs", ref_time, self._WINDOW_4H
            ),
            "insulin_sum_2h": self._log_sum_in_window(
                context.log_entries, "insulin", ref_time, self._WINDOW_2H
            ),
            "insulin_sum_4h": self._log_sum_in_window(
                context.log_entries, "insulin", ref_time, self._WINDOW_4H
            ),
            "basal_rate_u_h": self._basal_rate(context),
            "insulin_action_hours": self._insulin_action_hours(context),
            "correction_factor": self._correction_factor(context),
            "hour_sin": self._hour_sin(ref_time),
            "hour_cos": self._hour_cos(ref_time),
        }
        return _FeatureRow(**kwargs)

    # ── validation ──────────────────────────────────────────────────

    def _validate_context(self, context: FeatureContext) -> None:
        """Raise InsufficientContextError if data is too sparse or stale."""
        if not context.glucose_readings:
            raise InsufficientContextError("no_glucose_data", context)

        ref_time = context.reference_time
        latest_ts = max(
            (
                r.timestamp
                for r in context.glucose_readings
                if r.timestamp is not None
            ),
            default=None,
        )
        if latest_ts is None:
            raise InsufficientContextError("no_glucose_data", context)

        # Check staleness: max allowed age of most recent reading
        age_s = (ref_time - latest_ts).total_seconds()
        if age_s > self._MAX_BG_AGE_S:
            raise InsufficientContextError("stale_glucose_data", context)

        if len(context.glucose_readings) < self._MIN_BG_COUNT:
            raise InsufficientContextError("insufficient_glucose_count", context)

    # ── BG helpers ──────────────────────────────────────────────────

    @staticmethod
    def _extract_bg_series(
        context: FeatureContext,
    ) -> tuple[list[float], list[datetime]]:
        """Return (values, timestamps) sorted by timestamp ascending."""
        pairs: list[tuple[datetime, float]] = []
        for r in context.glucose_readings:
            if r.sgv is not None and r.timestamp is not None:
                pairs.append((r.timestamp, float(r.sgv)))
        pairs.sort(key=lambda x: x[0])
        return [v for _, v in pairs], [ts for ts, _ in pairs]

    @staticmethod
    def _mean_in_window(
        values: list[float],
        timestamps: list[datetime],
        ref_time: datetime,
        window: timedelta,
    ) -> float:
        """Mean of BG values within *window* before *ref_time*."""
        cutoff = ref_time - window
        subset = [
            v for v, ts in zip(values, timestamps, strict=False) if ts >= cutoff
        ]
        if not subset:
            return values[-1]  # fallback: latest value
        return sum(subset) / len(subset)

    @staticmethod
    def _slope_in_window(
        values: list[float],
        timestamps: list[datetime],
        ref_time: datetime,
        window: timedelta,
    ) -> float:
        """Rate of BG change (mg/dL per minute) via OLS regression.

        Returns 0.0 when fewer than 2 points are available in the window.
        """
        cutoff = ref_time - window
        subset = [
            (ts, v)
            for v, ts in zip(values, timestamps, strict=False)
            if ts >= cutoff
        ]
        if len(subset) < 2:
            return 0.0

        # Convert timestamps to minutes relative to first point
        base_minutes = subset[0][0].timestamp() / 60.0
        xs = [(ts.timestamp() / 60.0) - base_minutes for ts, _ in subset]
        ys = [v for _, v in subset]

        n = len(xs)
        x_mean = sum(xs) / n
        y_mean = sum(ys) / n
        num = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n))
        den = sum((x - x_mean) ** 2 for x in xs)

        if den == 0.0:
            return 0.0
        return num / den

    # ── log-entry helpers ───────────────────────────────────────────

    @staticmethod
    def _log_sum_in_window(
        log_entries: list[LogEntry],
        entry_type: str,
        ref_time: datetime,
        window: timedelta,
    ) -> float:
        """Sum of *value* for log entries of *entry_type* within window."""
        cutoff = ref_time - window
        from bgmon_api.models import LogEntryType  # noqa: PLC0415

        target_type = {
            "carbs": LogEntryType.CARBS,
            "insulin": LogEntryType.INSULIN,
        }.get(entry_type)
        if target_type is None:
            return 0.0

        total = 0.0
        for entry in log_entries:
            if entry.entry_type != target_type:
                continue
            if entry.created_at is None:
                continue
            ts = entry.created_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            if ts >= cutoff:
                total += float(entry.value)
        return total

    # ── basal / settings helpers ────────────────────────────────────

    @staticmethod
    def _basal_rate(context: FeatureContext) -> float:
        if context.basal_rate is not None:
            return float(context.basal_rate.rate)
        return 0.0

    @staticmethod
    def _insulin_action_hours(context: FeatureContext) -> float:
        if context.global_settings is not None:
            return float(context.global_settings.insulin_action_hours)
        return 4.0  # default

    @staticmethod
    def _correction_factor(context: FeatureContext) -> float:
        if context.global_settings is not None:
            return float(context.global_settings.correction_factor)
        return 50.0  # default

    # ── time-of-day encoding ────────────────────────────────────────

    @staticmethod
    def _hour_sin(reference_time: datetime) -> float:
        """sin(2π × hour / 24) — cyclical hour-of-day encoding."""
        hour = reference_time.hour + reference_time.minute / 60.0
        return math.sin(2.0 * math.pi * hour / 24.0)

    @staticmethod
    def _hour_cos(reference_time: datetime) -> float:
        """cos(2π × hour / 24) — cyclical hour-of-day encoding."""
        hour = reference_time.hour + reference_time.minute / 60.0
        return math.cos(2.0 * math.pi * hour / 24.0)
