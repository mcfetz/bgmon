"""Offline model training pipeline for BG prediction v1.

Trains separate scikit-learn regressors for each forecast horizon
(configured via BGMON_ML_HORIZONS) using walk-forward (TimeSeriesSplit)
validation, exposes feature-aligned targets via the existing feature
builder, and returns structured training results ready for publishing.

This module does NOT touch the database directly — callers feed in-memory
lists of GlucoseReading, LogEntry, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error

from bgmon_api.config import Config
from bgmon_api.services.feature_builder import (
    FeatureBuilder,
    FeatureContext,
    InsufficientContextError,
)
from bgmon_api.services.feature_builder import (
    feature_names as _canonical_feature_names,
)

if TYPE_CHECKING:
    from bgmon_api.services.feature_builder import (
        BasalRateHistory,
        GlobalSettings,
        GlucoseReading,
        LogEntry,
    )


# ── error types ────────────────────────────────────────────────────────


class TrainingInsufficientError(RuntimeError):
    """Raised when training cannot proceed — too few samples, no targets, etc."""


# ── data classes ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class HorizonMetrics:
    """Walk-forward validation metrics for a single forecast horizon."""

    horizon_minutes: int
    baseline_mae: float
    model_mae: float
    n_splits: int
    n_samples: int


@dataclass(frozen=True, slots=True)
class TrainerResult:
    """Complete output of a training run."""

    models: dict[int, LinearRegression]
    metrics: list[HorizonMetrics]
    feature_names: list[str]
    feature_version: str = "f1"
    model_version: str = "v1"
    train_window_start: datetime | None = None
    train_window_end: datetime | None = None
    trained_at: datetime | None = None

    @property
    def horizons(self) -> list[int]:
        """Sorted horizon minutes present in this result."""
        return sorted(self.models)


@dataclass(slots=True)
class TrainingInput:  # noqa: MUTABLE_OK — accumulator
    """Mutable accumulator with X rows + aligned targets for training.

    .add_context builds features per row; rows with insufficient context
    (e.g. first readings of the history window) are silently skipped.
    .to_arrays() returns filtered (X, y_by_horizon) — only rows where
    ALL horizon targets are non-None survive.
    """

    feature_rows: list[list[float]] = field(default_factory=list)
    targets: dict[int, list[float | None]] = field(default_factory=dict)
    window_start: datetime | None = None
    window_end: datetime | None = None
    sample_interval_s: float | None = None

    @property
    def sample_count(self) -> int:
        """Number of stored feature rows."""
        return len(self.feature_rows)

    def add_context(
        self,
        ref_time: datetime,
        targets: dict[int, float | None],
        glucose_readings: list[GlucoseReading],
        log_entries: list[LogEntry],
        basal_rate: BasalRateHistory | None,
        global_settings: GlobalSettings | None,
    ) -> None:
        """Extract features and record horizon targets, skip on failure."""
        try:
            ctx = FeatureContext(
                glucose_readings=glucose_readings,
                log_entries=log_entries,
                basal_rate=basal_rate,
                global_settings=global_settings,
                reference_time=ref_time,
            )
            feature_vec = FeatureBuilder().build_features(ctx).to_feature_vector()
        except InsufficientContextError:
            return

        self.feature_rows.append(feature_vec)
        for horizon, val in targets.items():
            self.targets.setdefault(horizon, []).append(val)

        if self.window_start is None or ref_time < self.window_start:
            self.window_start = ref_time
        if self.window_end is None or ref_time > self.window_end:
            self.window_end = ref_time

    def to_arrays(self) -> tuple[np.ndarray, dict[int, np.ndarray]]:
        """Return (feat_matrix, {horizon: y_array}) with None-target rows dropped.

        A row is dropped if ANY horizon has None as its target value.
        """
        if not self.targets:
            return np.empty((0, 0)), {}

        # Build mask: True if ALL horizons have non-None targets
        data = list(self.targets.values())
        mask = np.array(
            [all(v is not None for v in vals) for vals in zip(*data, strict=False)],
            dtype=bool,
        )

        feat = np.array(self.feature_rows, dtype=np.float64)[mask]
        y_by_horizon: dict[int, np.ndarray] = {}
        for horizon, vals in self.targets.items():
            y_by_horizon[horizon] = np.array(
                [v for v, ok in zip(vals, mask, strict=False) if ok],
                dtype=np.float64,
            )
        return feat, y_by_horizon


# ── walk-forward split helper ────────────────────────────────────────────


def _walk_forward_splits(
    n_samples: int,
    n_splits: int,
    test_size: int,
    gap: int = 0,
) -> list[tuple[int, int, int]]:
    """Return (train_end, test_start, test_end) triples for walk-forward CV.

    Folds are non-overlapping blocks walking backwards from the end of the
    series.  ``gap`` samples between ``train_end`` and ``test_start`` are
    excluded from BOTH sides — the gap MUST cover the forecast horizon
    expressed in samples, otherwise training data peeks into the test
    targets (leakage).
    """
    min_train = max(test_size * 4, n_samples // 4)
    splits: list[tuple[int, int, int]] = []
    for i in range(n_splits):
        test_end = n_samples - i * test_size
        test_start = test_end - test_size
        train_end = test_start - gap
        if train_end < min_train or test_start <= 0:
            continue
        splits.append((train_end, test_start, test_end))
    if splits:
        return sorted(splits)
    # Last resort: single split squeezed into whatever data exists
    fallback_test_start = max(1, n_samples - test_size)
    fallback_train_end = max(1, min(min_train, fallback_test_start))
    return [(fallback_train_end, fallback_test_start, n_samples)]


def _infer_sample_interval_s(training_input: TrainingInput) -> float:
    """Estimate median seconds between consecutive training rows.

    Prefers the measured median reading cadence recorded during
    collection; falls back to a span-based estimate.  The CV gap is
    derived from this value — underestimating it would let training data
    peek into test targets (leakage), so gaps inflate rather than shrink.
    """
    if training_input.sample_interval_s:
        return max(training_input.sample_interval_s, 1.0)
    if (
        training_input.window_start is not None
        and training_input.window_end is not None
        and training_input.sample_count > 1
    ):
        span_s = (
            training_input.window_end - training_input.window_start
        ).total_seconds()
        return max(span_s / (training_input.sample_count - 1), 1.0)
    return 300.0  # legacy assumption: 5-minute CGM cadence


# ── trainer ─────────────────────────────────────────────────────────────


class ModelTrainer:
    """Train and validate separate regressors per horizon with walk-forward CV.

    Usage::

        trainer = ModelTrainer(cv_splits=5)
        result = trainer.train(training_input)
    """

    def __init__(self, cv_splits: int = 5) -> None:
        self._cv_splits = cv_splits
        self._builder = FeatureBuilder()

    # ── public API ──────────────────────────────────────────────────

    def train(self, training_input: TrainingInput) -> TrainerResult:
        """Train horizon-specific regressors for each configured horizon.

        Raises:
            TrainingInsufficientError: when fewer than ``cv_splits + 1``
                valid (non-None-target) samples remain after alignment.
        """
        feat, y_by_horizon = training_input.to_arrays()  # noqa: N806

        if len(feat) < self._cv_splits + 1:
            raise TrainingInsufficientError(
                f"need at least {self._cv_splits + 1} valid samples, "
                f"got {len(feat)}"
            )

        interval_s = _infer_sample_interval_s(training_input)

        metrics: list[HorizonMetrics] = []
        models: dict[int, LinearRegression] = {}

        for horizon in Config.ML_HORIZONS:
            y = y_by_horizon[horizon]

            horizon_metrics = self._train_one_horizon(
                feat,
                y,
                horizon_minutes=horizon,
                n_splits=self._cv_splits,
                sample_interval_s=interval_s,
            )
            metrics.append(horizon_metrics)

            # Fit final production model on ALL data
            model = LinearRegression()
            model.fit(feat, y)
            models[horizon] = model

        trained_at = datetime.now(UTC)

        return TrainerResult(
            models=models,
            metrics=metrics,
            feature_names=_canonical_feature_names().copy(),
            model_version=trained_at.strftime("bgpred-%Y%m%dT%H%M%SZ"),
            train_window_start=training_input.window_start,
            train_window_end=training_input.window_end,
            trained_at=trained_at,
        )

    # ── internal ────────────────────────────────────────────────────

    def _train_one_horizon(
        self,
        feat: np.ndarray,  # noqa: N803 — standard ML notation
        y: np.ndarray,
        *,
        horizon_minutes: int,
        n_splits: int,
        sample_interval_s: float = 300.0,
    ) -> HorizonMetrics:
        """Walk-forward validation for a single horizon.

        The gap between training window and test block spans the full
        forecast horizon expressed in *actual* samples (derived from the
        real sampling interval), preventing data leakage.  Test blocks are
        sized so the reported MAE rests on hundreds of samples, not a
        handful.

        Baseline = always-predict-last-BG-value. Model = LinearRegression.
        """
        # Horizon-aware gap in SAMPLES from the real sampling cadence
        gap = max(1, int(np.ceil(horizon_minutes * 60 / sample_interval_s)))
        test_size = max(24, len(feat) // 50)

        if len(feat) < test_size + gap + 1:
            # Fall back to single-split — not ideal but survives tiny data
            splits = [(len(feat) - test_size - gap, len(feat) - test_size, len(feat))]
        else:
            splits = _walk_forward_splits(
                n_samples=len(feat),
                n_splits=n_splits,
                test_size=test_size,
                gap=gap,
            )

        model_maes: list[float] = []
        baseline_maes: list[float] = []
        split_count = 0

        for train_end, test_start, end in splits:
            X_train = feat[:train_end]  # noqa: N806
            X_test = feat[test_start:end]  # noqa: N806
            y_train, y_test = y[:train_end], y[test_start:end]

            model = LinearRegression()
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            model_maes.append(mean_absolute_error(y_test, y_pred))

            baseline_pred = X_test[:, 0]
            baseline_maes.append(mean_absolute_error(y_test, baseline_pred))

            split_count += 1

        return HorizonMetrics(
            horizon_minutes=horizon_minutes,
            baseline_mae=float(np.mean(baseline_maes)),
            model_mae=float(np.mean(model_maes)),
            n_splits=split_count,
            n_samples=len(feat),
        )
