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
    """Return (train_start, test_start, test_end) triples for walk-forward CV.

    Each fold expands the training window left-to-right, leaves a *gap*
    samples between train and test, and holds out *test_size* consecutive
    samples for validation.
    """
    min_train = max(1, (n_samples - (n_splits * (test_size + gap))) // 2)
    splits: list[tuple[int, int, int]] = []
    for i in range(n_splits):
        test_start = n_samples - (n_splits - i) * (test_size + gap)
        train_end = test_start - gap
        test_end = test_start + test_size
        if train_end < min_train or test_end > n_samples:
            continue
        splits.append((0, train_end, test_end))  # always start from 0
    return splits or [(0, n_samples - test_size, n_samples)]


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

        metrics: list[HorizonMetrics] = []
        models: dict[int, LinearRegression] = {}

        for horizon in Config.ML_HORIZONS:
            y = y_by_horizon[horizon]

            horizon_metrics = self._train_one_horizon(
                feat, y, horizon_minutes=horizon, n_splits=self._cv_splits
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
    ) -> HorizonMetrics:
        """Walk-forward validation for a single horizon.

        Uses a horizon-aware manual walk-forward split: expands training
        window left-to-right and holds out a contiguous test block of
        ``test_size`` samples.  A gap of ``horizon_minutes // 5`` samples
        is inserted between train and test to prevent data leakage from
        observations inside the forecast horizon.

        Baseline = always-predict-last-BG-value. Model = LinearRegression.
        """
        # Horizon-aware gap: prevent train data from peeking into the
        # forecast window.  5-minute sampling assumed.
        gap = max(1, horizon_minutes // 5)
        test_size = max(1, min(4, len(feat) // (n_splits * 2)))

        min_train_size = test_size + gap + 1
        if len(feat) < min_train_size * n_splits:
            # Fall back to single-split — not ideal but survives tiny data
            splits = [(0, len(feat) - test_size, len(feat))]
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

        for start, split_point, end in splits:
            X_train = feat[start:split_point]  # noqa: N806
            X_test = feat[split_point:end]  # noqa: N806
            y_train, y_test = y[start:split_point], y[split_point:end]

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
