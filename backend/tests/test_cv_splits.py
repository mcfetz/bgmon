"""Tests for leakage-safe walk-forward CV splits and cadence inference."""

import numpy as np
import pytest

from bgmon_api.services.model_trainer import (
    ModelTrainer,
    TrainingInput,
    _infer_sample_interval_s,
    _walk_forward_splits,
)


def test_splits_are_non_overlapping_and_gap_respected():
    n, n_splits, test_size, gap = 1000, 5, 24, 30
    splits = _walk_forward_splits(n, n_splits, test_size, gap)

    assert len(splits) == n_splits
    prev_test_end = None
    for train_end, test_start, test_end in splits:
        assert test_start - train_end == gap
        assert test_end - test_start == test_size
        if prev_test_end is not None:
            assert test_start >= prev_test_end  # no overlap between folds
        prev_test_end = test_end


def test_splits_cover_horizon_as_gap():
    """Gap must span the forecast horizon expressed in samples."""
    interval_s = 60.0  # 1-minute CGM cadence
    horizon_min = 30
    gap = int(np.ceil(horizon_min * 60 / interval_s))

    splits = _walk_forward_splits(5000, 5, test_size=24, gap=gap)
    for train_end, test_start, _test_end in splits:
        minutes_between = (test_start - train_end) * interval_s / 60.0
        assert minutes_between >= horizon_min


def test_splits_fallback_for_tiny_data():
    n = 40
    splits = _walk_forward_splits(n, 5, test_size=24, gap=10)
    assert len(splits) == 1
    train_end, test_start, test_end = splits[0]
    assert 1 <= train_end <= test_start < test_end <= n


def test_infer_interval_prefers_measured_cadence():
    ti = TrainingInput(sample_interval_s=60.0)
    assert _infer_sample_interval_s(ti) == 60.0


def test_infer_interval_falls_back_to_span():
    from datetime import UTC, datetime, timedelta

    rows = [[0.0] * 15 for _ in range(61)]
    ti = TrainingInput(
        feature_rows=rows,
        window_start=datetime(2026, 1, 1, tzinfo=UTC),
        window_end=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=1),
    )
    assert _infer_sample_interval_s(ti) == pytest.approx(60.0)


def test_infer_interval_default_without_context():
    assert _infer_sample_interval_s(TrainingInput()) == 300.0


def test_trainer_reports_metrics_on_all_cv_samples():
    """Regression: CV must evaluate on hundreds of samples, not a handful."""
    rng = np.random.default_rng(42)
    n = 600
    feat = np.column_stack([
        120 + np.cumsum(rng.normal(0, 1.5, n)),  # random-walk latest_bg
        rng.normal(0, 1, (n, 14)),
    ])
    y = feat[:, 0] + rng.normal(0, 5, n)

    ti = TrainingInput(
        feature_rows=feat.tolist(),
        targets={h: y.tolist() for h in (30, 60, 120)},
        sample_interval_s=60.0,
    )
    trainer = ModelTrainer(cv_splits=min(5, max(2, ti.sample_count - 1)))
    result = trainer.train(ti)

    m = result.metrics[0]
    total_test = m.n_splits * max(24, n // 50)
    assert total_test >= 100
    assert m.n_samples == len(feat)
