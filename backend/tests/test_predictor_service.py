"""Tests for runtime predictor service — plan task 5.

Covers all structured outcome paths:
  - disabled (ML disabled via env)
  - unavailable (missing artifacts)
  - insufficient_context (stale/missing BG)
  - ready 60m (successful prediction, 12 future points, persisted)
  - reuse (same context → cached run returned)

Pytest fixtures are often unused in test method signatures but required
for the app context and test isolation.
"""

# ruff: noqa: ARG002  # unused-method-argument — fixtures are intentional

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from sklearn.linear_model import LinearRegression

from bgmon_api.config import Config, MlRuntimeState
from bgmon_api.models import (
    BasalRateHistory,
    GlobalSettings,
    GlucoseReading,
    LogEntry,
    LogEntryType,
    PredictionPoint,
    PredictionRun,
)
from bgmon_api.services.feature_builder import (
    FeatureContext,
)
from bgmon_api.services.feature_builder import (
    feature_names as canonical_feature_names,
)
from bgmon_api.services.predictor import (
    DisabledOutcome,
    InsufficientContextOutcome,
    PredictorOutcomeKind,
    ReadyOutcome,
    UnavailableOutcome,
    _clear_cache,
    predict,
)

# ── helpers ───────────────────────────────────────────────────────────────


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


def _normal_context() -> FeatureContext:
    """6h BG history, sufficient for prediction."""
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
    log_entries = [
        _make_log(now - timedelta(minutes=90), LogEntryType.CARBS, 30.0),
        _make_log(now - timedelta(minutes=85), LogEntryType.INSULIN, 3.0),
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


def _empty_context() -> FeatureContext:
    return FeatureContext(
        glucose_readings=[],
        log_entries=[],
        basal_rate=None,
        global_settings=None,
        reference_time=datetime.now(UTC),
    )


def _write_fake_artifacts(
    model_dir: Path,
    *,
    model_version: str = "bgpred-test",
    feature_version: str = "f1",
    horizons: tuple[int, ...] = (60, 120),
) -> Path:
    """Create minimal 15-feature model artifacts and return manifest path.

    The feature vector produced by FeatureBuilder has 15 features, so
    the dummy model must accept a 15-element input.
    """
    import joblib  # noqa: PLC0415

    model_dir.mkdir(parents=True, exist_ok=True)
    model_files: dict[str, str] = {}
    expected_feature_names = canonical_feature_names()
    n_features = len(expected_feature_names)

    for horizon in horizons:
        # Train a trivial model on random data matching the real feature count.
        rng = np.random.RandomState(42)
        X = rng.randn(20, n_features)  # noqa: N806
        y = rng.randn(20) * 30 + 120.0
        model = LinearRegression()
        model.fit(X, y)
        fname = f"model_{horizon}m.joblib"
        model_files[f"{horizon}m"] = fname
        joblib.dump(model, model_dir / fname)

    manifest = {
        "model_version": model_version,
        "feature_version": feature_version,
        "horizons": list(horizons),
        "feature_names": expected_feature_names,
        "feature_count": n_features,
        "sklearn_version": "1.0.0",
        "trained_at": datetime.now(UTC).isoformat(),
        "train_window": {"start": None, "end": None},
        "metrics": [],
        "model_files": model_files,
    }
    manifest_path = model_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def _state_for_dir(model_dir: Path, *, horizons: tuple[int, ...] = (60,)) -> MlRuntimeState:
    """Build an MlRuntimeState pointing at *model_dir*."""
    return MlRuntimeState(
        enabled=True,
        status="ready",
        reason="ready",
        model_dir=model_dir,
        manifest_path=model_dir / "manifest.json",
        horizons=horizons,
        artifacts_available=True,
    )


def _patch_state(state: MlRuntimeState):
    """Return a patch context manager that makes Config return *state*."""
    return patch.object(Config, "ml_runtime_state", return_value=state)


# ── ML disabled ───────────────────────────────────────────────────────────


class TestMlDisabled:
    """Given: BGMON_ML_ENABLED is false → Then: DisabledOutcome, no DB writes."""

    def test_ml_disabled_returns_disabled_outcome(  # noqa: ARG002
        self, db_session, patient_user):
        _clear_cache()
        disabled_state = MlRuntimeState(
            enabled=False,
            status="disabled",
            reason="ml_disabled",
            model_dir=Path("/nonexistent"),
            manifest_path=Path("/nonexistent/manifest.json"),
            horizons=(60,),
            artifacts_available=False,
        )
        with _patch_state(disabled_state):
            result = predict(
                user_id=patient_user.id,
                feature_context=_normal_context(),
                horizon_minutes=60,
            )

        assert isinstance(result, DisabledOutcome)
        assert result.kind == PredictorOutcomeKind.DISABLED
        assert result.reason == "ml_disabled"

    def test_ml_disabled_no_db_writes(self, db_session, patient_user):
        _clear_cache()
        before_runs = db_session.query(PredictionRun).count()
        before_points = db_session.query(PredictionPoint).count()

        disabled_state = MlRuntimeState(
            enabled=False,
            status="disabled",
            reason="ml_disabled",
            model_dir=Path("/nonexistent"),
            manifest_path=Path("/nonexistent/manifest.json"),
            horizons=(60,),
            artifacts_available=False,
        )
        with _patch_state(disabled_state):
            predict(
                user_id=patient_user.id,
                feature_context=_normal_context(),
                horizon_minutes=60,
            )

        assert db_session.query(PredictionRun).count() == before_runs
        assert db_session.query(PredictionPoint).count() == before_points


# ── missing / invalid artifacts ───────────────────────────────────────────


class TestUnavailable:
    """Given: ML enabled but no artifacts → Then: UnavailableOutcome, no DB writes."""

    def test_missing_manifest_returns_unavailable(self, db_session, patient_user):  # noqa: ARG002
        _clear_cache()
        missing_state = MlRuntimeState(
            enabled=True,
            status="unavailable",
            reason="missing_manifest",
            model_dir=Path("/nonexistent"),
            manifest_path=Path("/nonexistent/manifest.json"),
            horizons=(60,),
            artifacts_available=False,
        )
        with _patch_state(missing_state):
            result = predict(
                user_id=patient_user.id,
                feature_context=_normal_context(),
                horizon_minutes=60,
            )

        assert isinstance(result, UnavailableOutcome)
        assert result.kind == PredictorOutcomeKind.UNAVAILABLE

    def test_missing_model_file_returns_unavailable(self, db_session, patient_user):  # noqa: ARG002
        _clear_cache()
        # Make a real temp dir with manifest but NO model files
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir)
            manifest = {
                "model_version": "test",
                "feature_version": "f1",
                "horizons": [60],
                "feature_names": [],
                "feature_count": 0,
                "sklearn_version": "1.0.0",
                "trained_at": datetime.now(UTC).isoformat(),
                "train_window": {"start": None, "end": None},
                "metrics": [],
                "model_files": {"60m": "model_60m.joblib"},
            }
            (model_dir / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            # Config will report unavailable because the .joblib files don't exist
            unavailable_state = MlRuntimeState(
                enabled=True,
                status="unavailable",
                reason="missing_model_artifact",
                model_dir=model_dir,
                manifest_path=model_dir / "manifest.json",
                horizons=(60,),
                artifacts_available=False,
            )
            with _patch_state(unavailable_state):
                result = predict(
                    user_id=patient_user.id,
                    feature_context=_normal_context(),
                    horizon_minutes=60,
                )

            assert isinstance(result, UnavailableOutcome)

    def test_unsupported_horizon_returns_unavailable(self, db_session, patient_user):  # noqa: ARG002
        _clear_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir)
            _write_fake_artifacts(model_dir, horizons=(60,))
            state = _state_for_dir(model_dir, horizons=(60,))
            with _patch_state(state):
                result = predict(
                    user_id=patient_user.id,
                    feature_context=_normal_context(),
                    horizon_minutes=999,  # not in state.horizons
                )

            assert isinstance(result, UnavailableOutcome)
            assert result.reason == "unsupported_horizon_999m"

    def test_invalid_manifest_feature_contract_returns_unavailable(
        self, db_session, patient_user,  # noqa: ARG002
    ):
        _clear_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir)
            _write_fake_artifacts(model_dir, horizons=(60,))
            manifest_path = model_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["feature_names"] = ["wrong_feature"]
            manifest["feature_count"] = 1
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            state = _state_for_dir(model_dir, horizons=(60,))
            with _patch_state(state):
                result = predict(
                    user_id=patient_user.id,
                    feature_context=_normal_context(),
                    horizon_minutes=60,
                )

            assert isinstance(result, UnavailableOutcome)

    def test_invalid_manifest_structure_returns_unavailable(
        self, db_session, patient_user,  # noqa: ARG002
    ):
        _clear_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir)
            _write_fake_artifacts(model_dir, horizons=(60,))
            manifest_path = model_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["model_files"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            state = _state_for_dir(model_dir, horizons=(60,))
            with _patch_state(state):
                result = predict(
                    user_id=patient_user.id,
                    feature_context=_normal_context(),
                    horizon_minutes=60,
                )

            assert isinstance(result, UnavailableOutcome)

    def test_unavailable_no_db_writes(self, db_session, patient_user):
        _clear_cache()
        before_runs = db_session.query(PredictionRun).count()
        missing_state = MlRuntimeState(
            enabled=True,
            status="unavailable",
            reason="missing_manifest",
            model_dir=Path("/nonexistent"),
            manifest_path=Path("/nonexistent/manifest.json"),
            horizons=(60,),
            artifacts_available=False,
        )
        with _patch_state(missing_state):
            predict(
                user_id=patient_user.id,
                feature_context=_normal_context(),
                horizon_minutes=60,
            )

        assert db_session.query(PredictionRun).count() == before_runs


# ── insufficient context ──────────────────────────────────────────────────


class TestInsufficientContext:
    """Given: stale or no BG data → Then: InsufficientContextOutcome, no DB writes."""

    def test_empty_bg_returns_insufficient_context(self, db_session, patient_user):  # noqa: ARG002
        _clear_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir)
            _write_fake_artifacts(model_dir, horizons=(60,))
            state = _state_for_dir(model_dir, horizons=(60,))
            with _patch_state(state):
                result = predict(
                    user_id=patient_user.id,
                    feature_context=_empty_context(),
                    horizon_minutes=60,
                )

            assert isinstance(result, InsufficientContextOutcome)
            assert result.kind == PredictorOutcomeKind.INSUFFICIENT_CONTEXT
            assert result.reason == "no_glucose_data"

    def test_insufficient_context_no_db_writes(self, db_session, patient_user):
        _clear_cache()
        before = db_session.query(PredictionRun).count()
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir)
            _write_fake_artifacts(model_dir, horizons=(60,))
            state = _state_for_dir(model_dir, horizons=(60,))
            with _patch_state(state):
                predict(
                    user_id=patient_user.id,
                    feature_context=_empty_context(),
                    horizon_minutes=60,
                )

        assert db_session.query(PredictionRun).count() == before


# ── successful prediction ─────────────────────────────────────────────────


class TestPredictSuccess:
    """Given: valid model + sufficient context → Then: ReadyOutcome with 12 points."""

    def test_60m_prediction_returns_ready_and_12_points(
        self, db_session, patient_user,
    ):
        _clear_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir)
            _write_fake_artifacts(model_dir, horizons=(60,))
            state = _state_for_dir(model_dir, horizons=(60,))
            ctx = _normal_context()
            with _patch_state(state):
                result = predict(
                    user_id=patient_user.id,
                    feature_context=ctx,
                    horizon_minutes=60,
                )

            assert isinstance(result, ReadyOutcome)
            assert result.kind == PredictorOutcomeKind.READY
            assert result.reused is False
            assert result.run_id > 0

            # Verify the run is persisted
            run = db_session.query(PredictionRun).filter_by(id=result.run_id).first()
            assert run is not None
            assert run.user_id == patient_user.id
            assert run.horizon_minutes == 60
            assert run.model_version == "bgpred-test"
            assert run.feature_version == "f1"
            assert run.context_end_at == ctx.reference_time

            # 60m → 12 points, each 5 min apart
            points = (
                db_session.query(PredictionPoint)
                .filter_by(run_id=run.id)
                .order_by(PredictionPoint.timestamp)
                .all()
            )
            assert len(points) == 12, f"expected 12 forecast points, got {len(points)}"

            # Timestamps must be strictly ordered in the future
            assert points[0].timestamp == ctx.reference_time + timedelta(minutes=5)
            for i in range(1, len(points)):
                assert points[i].timestamp > points[i - 1].timestamp
                assert points[i].timestamp == ctx.reference_time + timedelta(minutes=5 * (i + 1))

            # Each point has a predicted value (can be negative in test — the
            # prediction value is not validated, only the structure)
            for point in points:
                assert point.lower_bound is not None
                assert point.lower_bound == pytest.approx(point.predicted_sgv - 15.0)
                assert point.upper_bound is not None
                assert point.upper_bound == pytest.approx(point.predicted_sgv + 15.0)
                assert point.lower_bound < point.upper_bound

    def test_120m_prediction_returns_ready_and_24_points(
        self, db_session, patient_user,
    ):
        _clear_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir)
            _write_fake_artifacts(model_dir, horizons=(60, 120))
            state = _state_for_dir(model_dir, horizons=(60, 120))
            with _patch_state(state):
                result = predict(
                    user_id=patient_user.id,
                    feature_context=_normal_context(),
                    horizon_minutes=120,
                )

            assert isinstance(result, ReadyOutcome)
            points = (
                db_session.query(PredictionPoint)
                .filter_by(run_id=result.run_id)
                .all()
            )
            assert len(points) == 24, f"expected 24 forecast points, got {len(points)}"


# ── same-context reuse ────────────────────────────────────────────────────


class TestContextReuse:
    """Given: same context tuple → Then: previous run is returned, no new rows."""

    def test_same_context_reuses_cached_run(self, db_session, patient_user):
        _clear_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir)
            _write_fake_artifacts(model_dir, horizons=(60,))
            state = _state_for_dir(model_dir, horizons=(60,))
            ctx = _normal_context()

            with _patch_state(state):
                first = predict(
                    user_id=patient_user.id,
                    feature_context=ctx,
                    horizon_minutes=60,
                )
                assert isinstance(first, ReadyOutcome)
                assert first.reused is False
                first_run_id = first.run_id

                # Clear in-memory cache to test DB-level reuse
                _clear_cache()

                second = predict(
                    user_id=patient_user.id,
                    feature_context=ctx,
                    horizon_minutes=60,
                )
                assert isinstance(second, ReadyOutcome)
                assert second.reused is True
                assert second.run_id == first_run_id

                # No new runs created
                runs = (
                    db_session.query(PredictionRun)
                    .filter_by(user_id=patient_user.id, horizon_minutes=60)
                    .all()
                )
                assert len(runs) == 1

    def test_different_context_creates_new_run(self, db_session, patient_user):
        _clear_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir)
            _write_fake_artifacts(model_dir, horizons=(60,))
            state = _state_for_dir(model_dir, horizons=(60,))

            with _patch_state(state):
                ctx1 = _normal_context()
                # Shift reference_time by 5 minutes for context2
                now = datetime.now(UTC)
                base = now - timedelta(hours=6)
                bg_readings = [
                    _make_bg(base + timedelta(minutes=i * 10), 115)
                    for i in range(36)
                ]
                ctx2 = FeatureContext(
                    glucose_readings=bg_readings,
                    log_entries=[],
                    basal_rate=None,
                    global_settings=None,
                    reference_time=now + timedelta(minutes=5),
                )

                first = predict(
                    user_id=patient_user.id,
                    feature_context=ctx1,
                    horizon_minutes=60,
                )
                _clear_cache()
                second = predict(
                    user_id=patient_user.id,
                    feature_context=ctx2,
                    horizon_minutes=60,
                )

                assert isinstance(first, ReadyOutcome)
                assert isinstance(second, ReadyOutcome)
                assert first.reused is False
                assert second.reused is False
                assert first.run_id != second.run_id


# ── outcome type completeness ─────────────────────────────────────────────

# The union PredictorOutcome covers all 4 branches.
# Each branch is tested above; this ensures the union works at type level.


class TestPredictorOutcomeUnion:
    """Structural checks on the outcome type hierarchy."""

    def test_all_outcomes_have_kind_and_reason(self):
        """Every outcome must expose kind: str and reason: str."""
        from bgmon_api.services.predictor import (
            DisabledOutcome,
            InsufficientContextOutcome,
            ReadyOutcome,
            UnavailableOutcome,
        )

        for cls in (
            DisabledOutcome,
            UnavailableOutcome,
            InsufficientContextOutcome,
            ReadyOutcome,
        ):
            instance = cls()
            assert isinstance(instance.kind, str)
            assert isinstance(instance.reason, str)

    def test_ready_outcome_has_run_id(self):
        outcome = ReadyOutcome(run_id=42, reused=True)
        assert outcome.run_id == 42
        assert outcome.reused is True
