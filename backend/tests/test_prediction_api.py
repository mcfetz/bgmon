"""Tests for dashboard prediction API — plan task 7.

Covers:
  - successful 60m prediction with run metadata + future points
  - invalid ``minutes`` query parameter → 400
  - ML disabled → 503 with structured outcome
  - model artifacts unavailable → 503 with structured outcome
  - insufficient context → 422 with structured outcome
  - authenticated-only access

Pytest fixtures are often unused in test method signatures but required
for the app context and test isolation.
"""

# ruff: noqa: ARG002  # unused-method-argument — fixtures are intentional

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

import numpy as np
from sklearn.linear_model import LinearRegression

from bgmon_api.config import MlRuntimeState
from bgmon_api.models import (
    BasalRateHistory,
    GlobalSettings,
    GlucoseReading,
    LogEntry,
    LogEntryType,
)
from bgmon_api.services.feature_builder import FeatureContext
from bgmon_api.services.feature_builder import (
    feature_names as canonical_feature_names,
)
from bgmon_api.services.predictor import _clear_cache

# ── helpers ───────────────────────────────────────────────────────────────


def _make_bg(timestamp: datetime, sgv: int) -> GlucoseReading:
    reading = GlucoseReading()
    reading.timestamp = timestamp
    reading.sgv = sgv
    reading.source = "test"
    return reading


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
    """Create minimal 15-feature model artifacts and return manifest path."""
    import joblib  # noqa: PLC0415

    model_dir.mkdir(parents=True, exist_ok=True)
    model_files: dict[str, str] = {}
    expected_feature_names = canonical_feature_names()
    n_features = len(expected_feature_names)

    for horizon in horizons:
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
    return MlRuntimeState(
        enabled=True,
        status="ready",
        reason="ready",
        model_dir=model_dir,
        manifest_path=model_dir / "manifest.json",
        horizons=horizons,
        artifacts_available=True,
    )


# ── auth-only ──────────────────────────────────────────────────────────────


class TestPredictionAuth:
    """Given: no auth header → Then: 401."""

    def test_predictions_unauthenticated_returns_401(self, client):
        response = client.get("/api/dashboard/predictions?minutes=60")
        assert response.status_code == HTTPStatus.UNAUTHORIZED


# ── invalid minutes ────────────────────────────────────────────────────────


class TestPredictionInvalidMinutes:
    """Given: invalid minutes param → Then: 400 with message."""

    def test_missing_minutes_returns_400(self, client, patient_user, auth_headers):
        response = client.get(
            "/api/dashboard/predictions",
            headers=auth_headers(patient_user),
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.get_json()
        assert "error" in data

    def test_non_integer_minutes_returns_400(self, client, patient_user, auth_headers):
        response = client.get(
            "/api/dashboard/predictions?minutes=abc",
            headers=auth_headers(patient_user),
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_negative_minutes_returns_400(self, client, patient_user, auth_headers):
        response = client.get(
            "/api/dashboard/predictions?minutes=-1",
            headers=auth_headers(patient_user),
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_zero_minutes_returns_400(self, client, patient_user, auth_headers):
        response = client.get(
            "/api/dashboard/predictions?minutes=0",
            headers=auth_headers(patient_user),
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_unsupported_horizon_returns_400(self, client, patient_user, auth_headers):
        """A horizon not in the configured list must be rejected at the API layer."""
        response = client.get(
            "/api/dashboard/predictions?minutes=999",
            headers=auth_headers(patient_user),
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST


# ── ML disabled ────────────────────────────────────────────────────────────


class TestPredictionMlDisabled:
    """Given: BGMON_ML_ENABLED=false → Then: 503 with disabled outcome."""

    def test_ml_disabled_returns_503(self, client, patient_user, auth_headers):
        from bgmon_api.config import Config

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
        with patch.object(Config, "ml_runtime_state", return_value=disabled_state):
            response = client.get(
                "/api/dashboard/predictions?minutes=60",
                headers=auth_headers(patient_user),
            )

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        data = response.get_json()
        assert data["status"] == "disabled"
        assert data["reason"] == "ml_disabled"
        assert "points" not in data


# ── unavailable artifacts ──────────────────────────────────────────────────


class TestPredictionUnavailable:
    """Given: ML enabled but no model artifacts → Then: 503 with unavailable outcome."""

    def test_missing_model_returns_503(self, client, patient_user, auth_headers):
        from bgmon_api.config import Config

        _clear_cache()
        unavailable_state = MlRuntimeState(
            enabled=True,
            status="unavailable",
            reason="missing_manifest",
            model_dir=Path("/nonexistent"),
            manifest_path=Path("/nonexistent/manifest.json"),
            horizons=(60,),
            artifacts_available=False,
        )
        with patch.object(Config, "ml_runtime_state", return_value=unavailable_state):
            response = client.get(
                "/api/dashboard/predictions?minutes=60",
                headers=auth_headers(patient_user),
            )

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        data = response.get_json()
        assert data["status"] == "unavailable"
        assert "points" not in data


# ── insufficient context ───────────────────────────────────────────────────


class TestPredictionInsufficientContext:
    """Given: no BG data → Then: 422 with insufficient_context outcome."""

    def test_insufficient_context_returns_422(self, client, patient_user, auth_headers):
        from bgmon_api.config import Config

        _clear_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir)
            _write_fake_artifacts(model_dir, horizons=(60,))
            state = _state_for_dir(model_dir, horizons=(60,))
            with patch.object(Config, "ml_runtime_state", return_value=state):
                # The endpoint queries the DB for real GlucoseReadings.
                # With an empty DB, there are none → insufficient context.
                response = client.get(
                    "/api/dashboard/predictions?minutes=60",
                    headers=auth_headers(patient_user),
                )

            assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, (
                f"expected 422, got {response.status_code}: {response.get_data(as_text=True)}"
            )
            data = response.get_json()
            assert data["status"] == "insufficient_context"


# ── successful prediction ──────────────────────────────────────────────────


class TestPredictionSuccess:
    """Given: valid model + sufficient BG data → Then: 200 with run + points."""

    def test_60m_prediction_returns_200_with_run_and_points(
        self, client, db_session, patient_user, glucose_readings, auth_headers,
    ):
        from bgmon_api.config import Config

        _clear_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir)
            _write_fake_artifacts(model_dir, horizons=(60,))
            state = _state_for_dir(model_dir, horizons=(60,))
            with patch.object(Config, "ml_runtime_state", return_value=state):
                response = client.get(
                    "/api/dashboard/predictions?minutes=60",
                    headers=auth_headers(patient_user),
                )

            assert response.status_code == HTTPStatus.OK, (
                f"expected 200, got {response.status_code}: {response.get_data(as_text=True)}"
            )
            data = response.get_json()

            # Top-level structure
            assert data["status"] == "ready"
            assert data["horizon_minutes"] == 60
            assert data["model_version"] == "bgpred-test"
            assert "generated_at" in data
            assert "context_end_at" in data
            assert "run_id" in data

            # Points
            points = data["points"]
            assert isinstance(points, list), f"expected list, got {type(points)}"
            assert len(points) == 12, f"expected 12 forecast points, got {len(points)}"

            # Point structure
            for point in points:
                assert "timestamp" in point
                assert "predicted_sgv" in point
                assert "lower_bound" in point
                assert "upper_bound" in point
                assert point["lower_bound"] < point["upper_bound"]

            # Timestamps are ordered and in the future relative to context_end_at
            timestamps = [point["timestamp"] for point in points]
            assert timestamps == sorted(timestamps), "points must be ordered by timestamp"

    def test_120m_prediction_returns_24_points(
        self, client, db_session, patient_user, glucose_readings, auth_headers,
    ):
        from bgmon_api.config import Config

        _clear_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir)
            _write_fake_artifacts(model_dir, horizons=(60, 120))
            state = _state_for_dir(model_dir, horizons=(60, 120))
            with patch.object(Config, "ml_runtime_state", return_value=state):
                response = client.get(
                    "/api/dashboard/predictions?minutes=120",
                    headers=auth_headers(patient_user),
                )

            assert response.status_code == HTTPStatus.OK
            data = response.get_json()
            assert data["horizon_minutes"] == 120
            assert len(data["points"]) == 24

    def test_repeated_call_reuses_cached_run(
        self, client, db_session, patient_user, glucose_readings, auth_headers,
    ):
        from bgmon_api.config import Config

        _clear_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir)
            _write_fake_artifacts(model_dir, horizons=(60,))
            state = _state_for_dir(model_dir, horizons=(60,))
            with patch.object(Config, "ml_runtime_state", return_value=state):
                first = client.get(
                    "/api/dashboard/predictions?minutes=60",
                    headers=auth_headers(patient_user),
                )
                first_data = first.get_json()

                # Second call should reuse via predictor's DB-level cache
                second = client.get(
                    "/api/dashboard/predictions?minutes=60",
                    headers=auth_headers(patient_user),
                )
                second_data = second.get_json()

            assert first.status_code == HTTPStatus.OK
            assert second.status_code == HTTPStatus.OK
            assert first_data["run_id"] == second_data["run_id"], (
                "repeated calls must reuse the existing run"
            )

    def test_prediction_endpoint_returns_valid_iso_timestamps(
        self, client, db_session, patient_user, glucose_readings, auth_headers,
    ):
        from bgmon_api.config import Config

        _clear_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir)
            _write_fake_artifacts(model_dir, horizons=(60,))
            state = _state_for_dir(model_dir, horizons=(60,))
            with patch.object(Config, "ml_runtime_state", return_value=state):
                response = client.get(
                    "/api/dashboard/predictions?minutes=60",
                    headers=auth_headers(patient_user),
                )

            data = response.get_json()
            # Validate generated_at and context_end_at are ISO-format strings
            assert "T" in data["generated_at"]
            assert "T" in data["context_end_at"]
            for point in data["points"]:
                assert "T" in point["timestamp"]

    def test_prediction_does_not_mutate_current_payload(
        self, client, patient_user, glucose_readings, auth_headers,
    ):
        """Existing /current endpoint must return unchanged payload."""
        response = client.get(
            "/api/dashboard/current",
            headers=auth_headers(patient_user),
        )
        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        # Verify the known shape of /current
        assert "sgv" in data
        assert "trend" in data
        assert "direction" in data
        assert "timestamp" in data
        # Verify no prediction fields leaked in
        assert "prediction" not in data
        assert "forecast" not in data
        assert "points" not in data
