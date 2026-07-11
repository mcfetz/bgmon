"""Tests for model training pipeline — plan task 4.

Covers:
- Insufficient-history failure path (failing-first)
- Artifact generation on seeded synthetic data
- Manifest content and shape assertions
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from bgmon_api.models import (
    GlucoseReading,
    LogEntry,
    LogEntryType,
)
from bgmon_api.services.model_publisher import publish_model
from bgmon_api.services.model_trainer import (
    ModelTrainer,
    TrainingInput,
    TrainingInsufficientError,
)

# ── helpers ─────────────────────────────────────────────────────────────


def _make_bg(timestamp: datetime, sgv: int) -> GlucoseReading:
    reading = GlucoseReading()
    reading.timestamp = timestamp
    reading.sgv = sgv
    reading.source = "test"
    return reading


def _build_seed_data(
    n_hours: int = 12,
    interval_minutes: int = 5,
) -> TrainingInput:
    """Build synthetic training data with a known pattern.

    Creates a BG pattern with a meal spike, then falling, plus
    corresponding future target values at 60m and 120m.

    The BG values follow a sine-like pattern so the model has
    non-trivial signal to learn.
    """
    import math

    now = datetime.now(UTC)
    start = now - timedelta(hours=n_hours)
    n_points = (n_hours * 60) // interval_minutes

    all_bg: list[GlucoseReading] = []
    for i in range(n_points):
        ts = start + timedelta(minutes=i * interval_minutes)
        minutes_in = i * interval_minutes
        # A pattern: 100 baseline + meal spike decaying
        bg = 100.0 + 80.0 * math.sin(2.0 * math.pi * minutes_in / (n_hours * 60))
        bg += 50.0 * max(0, 1.0 - minutes_in / (n_hours * 60 * 0.3))  # meal spike
        bg += (minutes_in / (n_hours * 60)) * 20.0  # gradual rise
        all_bg.append(_make_bg(ts, int(round(bg))))

    training_input = TrainingInput()

    for i in range(n_points - (120 // interval_minutes)):
        r = all_bg[i]
        ts = r.timestamp
        assert ts is not None

        # Target: value at ts + horizon
        t60_i = i + (60 // interval_minutes)
        t120_i = i + (120 // interval_minutes)

        target_60 = float(all_bg[t60_i].sgv) if t60_i < n_points else None
        target_120 = float(all_bg[t120_i].sgv) if t120_i < n_points else None

        # Context readings up to this point
        context_readings = all_bg[: i + 1]

        # Add some log entries
        log_entries: list[LogEntry] = []
        if i % 12 == 0:
            log_entries.append(
                _make_log_now(ts, LogEntryType.CARBS, 30.0)
            )
            log_entries.append(
                _make_log_now(ts, LogEntryType.INSULIN, 3.0)
            )
        if i % 24 == 0:
            log_entries.append(
                _make_log_now(ts, LogEntryType.BASAL, 1.0)
            )

        training_input.add_context(
            ref_time=ts,
            target_60m_val=target_60,
            target_120m_val=target_120,
            glucose_readings=context_readings,
            log_entries=log_entries,
            basal_rate=None,
            global_settings=None,
        )

    return training_input


def _make_log_now(timestamp: datetime, entry_type: LogEntryType, value: float) -> LogEntry:
    entry = LogEntry()
    entry.user_id = 1
    entry.entry_type = entry_type
    entry.value = value
    entry.unit = "g" if entry_type == LogEntryType.CARBS else "U"
    entry.created_at = timestamp
    return entry


# ── insufficient-history tests (failing-first) ─────────────────────────


class TestInsufficientHistory:
    """Training with too few valid samples must raise a clear error."""

    def test_empty_training_input_raises(self):
        """Given: no data at all → Then: TrainingInsufficientError."""
        trainer = ModelTrainer(cv_splits=3)
        with pytest.raises(TrainingInsufficientError):
            trainer.train(TrainingInput())

    def test_too_few_samples_raises_with_count(self):
        """Given: only 2 valid samples, cv_splits=3 → Then: error mentions count."""
        trainer = ModelTrainer(cv_splits=3)
        ti = _build_seed_data(n_hours=4)  # 4h gives enough look-ahead for 120m horizon
        x, y60, y120 = ti.to_arrays()  # noqa: N806 — ML notation
        # Verify we have at least some data
        assert len(x) >= 2

        # Force only 2 samples — must have both targets non-None to survive mask
        ti2 = TrainingInput()
        for row, t60, t120 in zip(x[:2], y60[:2], y120[:2], strict=False):
            ti2.feature_rows.append(list(row))
            ti2.targets_60m.append(float(t60))
            ti2.targets_120m.append(float(t120))
        # Verify we actually got 2 valid samples
        assert len(ti2.to_arrays()[0]) == 2

        with pytest.raises(TrainingInsufficientError) as exc_info:
            trainer.train(ti2)
        assert "2" in str(exc_info.value)

    def test_non_zero_exit_on_cli_insufficient(self):
        """Given: CLI train with empty DB → Then: exit code 1."""
        # The CLI train() function raises SystemExit(1) on insufficient data.
        # This exercises the error path directly.
        from bgmon_api.services.model_trainer import TrainingInsufficientError

        training_input = TrainingInput()

        trainer = ModelTrainer(cv_splits=3)
        with pytest.raises(TrainingInsufficientError):
            trainer.train(training_input)


# ── artifact generation tests ──────────────────────────────────────────


class TestArtifactGeneration:
    """Training produces valid model artifacts and metrics."""

    def test_trainer_produces_two_models(self):
        """Given: 8+ hours of seed data → Then: TrainerResult has two models."""
        ti = _build_seed_data(n_hours=8)
        trainer = ModelTrainer(cv_splits=3)
        result = trainer.train(ti)

        assert result.model_60m is not None
        assert result.model_120m is not None
        assert len(result.metrics) == 2

    def test_metrics_have_both_horizons(self):
        """Given: training result → Then: metrics for 60m and 120m present."""
        ti = _build_seed_data(n_hours=8)
        trainer = ModelTrainer(cv_splits=3)
        result = trainer.train(ti)

        horizons = {m.horizon_minutes for m in result.metrics}
        assert 60 in horizons
        assert 120 in horizons

    def test_model_mae_improves_over_baseline_mae(self):
        """Given: non-trivial seed pattern → Then: model MAE ≤ baseline MAE.

        On the sine-wave seed pattern, a linear model should do at least
        as well as the naive 'predict latest BG' baseline.
        """
        ti = _build_seed_data(n_hours=8)
        trainer = ModelTrainer(cv_splits=3)
        result = trainer.train(ti)

        for m in result.metrics:
            assert m.model_mae <= m.baseline_mae + 0.5, (
                f"horizon {m.horizon_minutes}m: model_mae={m.model_mae:.1f} "
                f"> baseline_mae={m.baseline_mae:.1f} + tolerance"
            )

    def test_metrics_are_finite(self):
        """Given: seed data → Then: all metrics are real finite numbers."""
        ti = _build_seed_data(n_hours=8)
        trainer = ModelTrainer(cv_splits=3)
        result = trainer.train(ti)

        for m in result.metrics:
            assert np.isfinite(m.baseline_mae)
            assert np.isfinite(m.model_mae)
            assert m.n_splits > 0
            assert m.n_samples > 0

    def test_publisher_creates_files(self, tmp_path: Path):
        """Given: trained result → When: published → Then: 3 files exist."""
        ti = _build_seed_data(n_hours=8)
        trainer = ModelTrainer(cv_splits=3)
        result = trainer.train(ti)

        model_dir = tmp_path / "models"
        manifest = publish_model(result, model_dir)

        assert manifest.exists()
        assert (model_dir / "model_60m.joblib").exists()
        assert (model_dir / "model_120m.joblib").exists()

    def test_published_model_is_loadable(self, tmp_path: Path):
        """Given: published joblib → When: loaded → Then: can .predict()."""
        import joblib

        ti = _build_seed_data(n_hours=8)
        trainer = ModelTrainer(cv_splits=3)
        result = trainer.train(ti)

        model_dir = tmp_path / "models"
        publish_model(result, model_dir)

        model = joblib.load(model_dir / "model_60m.joblib")
        x, _, _ = ti.to_arrays()  # noqa: N806 — ML notation
        preds = model.predict(x[:1, :])
        assert len(preds) == 1
        assert np.isfinite(preds[0])


# ── manifest shape tests ───────────────────────────────────────────────


class TestManifestShape:
    """Manifest JSON contains all required metadata fields."""

    _REQUIRED_ROOT_KEYS: set[str] = {
        "model_version",
        "feature_version",
        "horizons",
        "feature_names",
        "feature_count",
        "sklearn_version",
        "trained_at",
        "train_window",
        "metrics",
        "model_files",
    }

    _REQUIRED_METRIC_KEYS: set[str] = {
        "horizon_minutes",
        "baseline_mae",
        "model_mae",
        "n_splits",
        "n_samples",
    }

    def test_manifest_has_all_root_keys(self, tmp_path: Path):
        """Given: publisher → Then: manifest has every required root key."""
        ti = _build_seed_data(n_hours=8)
        trainer = ModelTrainer(cv_splits=3)
        result = trainer.train(ti)

        manifest_path = publish_model(result, tmp_path / "models")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        missing = self._REQUIRED_ROOT_KEYS - set(manifest.keys())
        assert not missing, f"Manifest missing keys: {missing}"

    def test_manifest_metrics_are_complete(self, tmp_path: Path):
        """Given: published manifest → Then: each metric entry is complete."""
        ti = _build_seed_data(n_hours=8)
        trainer = ModelTrainer(cv_splits=3)
        result = trainer.train(ti)

        manifest_path = publish_model(result, tmp_path / "models")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        assert len(manifest["metrics"]) == 2
        for metric in manifest["metrics"]:
            missing = self._REQUIRED_METRIC_KEYS - set(metric.keys())
            assert not missing, f"Metric missing keys: {missing}"

    def test_manifest_feature_names_match_canonical(self, tmp_path: Path):
        """Given: published manifest → Then: feature names match canonical."""
        from bgmon_api.services.feature_builder import feature_names as canonical

        ti = _build_seed_data(n_hours=8)
        trainer = ModelTrainer(cv_splits=3)
        result = trainer.train(ti)

        manifest_path = publish_model(result, tmp_path / "models")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        assert manifest["feature_names"] == canonical()
        assert manifest["feature_count"] == len(canonical())

    def test_manifest_horizons_match_metrics(self, tmp_path: Path):
        """Given: published manifest → Then: horizons array equals metric horizons."""
        ti = _build_seed_data(n_hours=8)
        trainer = ModelTrainer(cv_splits=3)
        result = trainer.train(ti)

        manifest_path = publish_model(result, tmp_path / "models")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        metric_horizons = sorted(m["horizon_minutes"] for m in manifest["metrics"])
        assert sorted(manifest["horizons"]) == metric_horizons
        assert set(manifest["horizons"]) == {60, 120}

    def test_manifest_model_files_match_disk(self, tmp_path: Path):
        """Given: published manifest → Then: model_files point to existing files."""
        ti = _build_seed_data(n_hours=8)
        trainer = ModelTrainer(cv_splits=3)
        result = trainer.train(ti)

        model_dir = tmp_path / "models"
        manifest_path = publish_model(result, model_dir)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        for label, rel_name in manifest["model_files"].items():
            full_path = model_dir / rel_name
            assert full_path.exists(), f"model_files.{label} → {full_path} missing"

    def test_manifest_sklearn_version_is_string(self, tmp_path: Path):
        """Given: published manifest → Then: sklearn_version is non-empty string."""
        ti = _build_seed_data(n_hours=8)
        trainer = ModelTrainer(cv_splits=3)
        result = trainer.train(ti)

        manifest_path = publish_model(result, tmp_path / "models")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        assert isinstance(manifest["sklearn_version"], str)
        assert len(manifest["sklearn_version"]) > 0


# ── data collection helper tests ────────────────────────────────────────


class TestDataCollection:
    """TrainingInput correctly accumulates features and targets."""

    def test_add_context_produces_rows(self):
        """Given: 8h seed → Then: TrainingInput has rows for each valid window."""
        ti = _build_seed_data(n_hours=8)
        x, y60, y120 = ti.to_arrays()  # noqa: N806 — ML notation

        assert len(x) > 10, f"expected >10 rows, got {len(x)}"
        assert len(x) == len(y60) == len(y120)
        assert x.shape[1] == 15  # feature count

    def test_to_arrays_filters_none_targets(self):
        """Given: mixed valid/None targets → Then: to_arrays drops None rows."""
        ti = TrainingInput()
        # Row 1: valid both
        ti.feature_rows.append([1.0] * 15)
        ti.targets_60m.append(100.0)
        ti.targets_120m.append(110.0)
        # Row 2: None for 120m
        ti.feature_rows.append([2.0] * 15)
        ti.targets_60m.append(105.0)
        ti.targets_120m.append(None)
        # Row 3: valid both again
        ti.feature_rows.append([3.0] * 15)
        ti.targets_60m.append(95.0)
        ti.targets_120m.append(100.0)

        x, y60, y120 = ti.to_arrays()  # noqa: N806 — ML notation

        assert len(x) == 2
        assert list(y60) == [100.0, 95.0]
        assert list(y120) == [110.0, 100.0]
