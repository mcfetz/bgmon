"""Tests for ML prediction configuration surface (plan task 1)."""

import os

from bgmon_api.config import Config


class TestMlConfigDefaults:
    """Config.ML_ENABLED, ML_MODEL_PATH, and ml_horizons() exist with safe defaults."""

    def test_ml_enabled_defaults_to_false(self):
        assert hasattr(Config, "ML_ENABLED"), "Config.ML_ENABLED must exist"
        assert Config.ML_ENABLED is False

    def test_ml_model_path_defaults_to_artifact_dir(self):
        assert hasattr(Config, "ML_MODEL_PATH"), "Config.ML_MODEL_PATH must exist"
        assert Config.ML_MODEL_PATH is not None
        assert isinstance(Config.ML_MODEL_PATH, str)
        assert Config.ML_MODEL_PATH.endswith("ml_models/bg_prediction_v1")

    def test_ml_horizons_defaults_to_60_and_120(self):
        assert hasattr(Config, "ML_HORIZONS"), "Config.ML_HORIZONS must exist"
        assert Config.ML_HORIZONS == [60, 120]
        assert callable(Config.ml_horizons), "Config.ml_horizons must be callable"
        horizons = Config.ml_horizons()
        assert isinstance(horizons, list)
        assert horizons == [60, 120]

    def test_ml_horizons_immutable(self):
        h1 = Config.ml_horizons()
        h2 = Config.ml_horizons()
        assert h1 is not h2, "ml_horizons() must return a fresh list each call"


class TestMlConfigEnvOverride:
    """Env vars override ML config defaults at access time."""

    def test_ml_enabled_env_true(self, monkeypatch):
        monkeypatch.setenv("BGMON_ML_ENABLED", "1")
        assert Config.ml_enabled() is True

    def test_ml_enabled_env_false_string(self, monkeypatch):
        monkeypatch.setenv("BGMON_ML_ENABLED", "false")
        assert Config.ml_enabled() is False

    def test_ml_model_path_env_override(self, monkeypatch):
        monkeypatch.setenv("BGMON_ML_MODEL_PATH", "/custom/model/path")
        assert Config.ml_model_path() == "/custom/model/path"

    def test_ml_horizons_env_override(self, monkeypatch):
        monkeypatch.setenv("BGMON_ML_HORIZONS", "30,60")
        assert Config.ml_horizons() == [30, 60]

    def test_ml_horizons_env_single(self, monkeypatch):
        monkeypatch.setenv("BGMON_ML_HORIZONS", "90")
        assert Config.ml_horizons() == [90]


class TestMlConfigUnavailableState:
    """Controlled unavailable state when model artifacts are missing."""

    def test_ml_runtime_state_disabled(self, monkeypatch):
        monkeypatch.setenv("BGMON_ML_ENABLED", "false")

        state = Config.ml_runtime_state()

        assert state.status == "disabled"
        assert state.enabled is False
        assert state.artifacts_available is False
        assert state.reason == "ml_disabled"

    def test_is_ml_available_false_when_disabled(self, monkeypatch):
        monkeypatch.setenv("BGMON_ML_ENABLED", "false")
        assert Config.ml_enabled() is False
        assert Config.is_ml_available() is False

    def test_ml_runtime_state_unavailable_when_manifest_missing(self, monkeypatch, tmp_path):
        model_dir = tmp_path / "bg_prediction_v1"
        model_dir.mkdir()
        monkeypatch.setenv("BGMON_ML_ENABLED", "true")
        monkeypatch.setenv("BGMON_ML_MODEL_PATH", str(model_dir))

        state = Config.ml_runtime_state()

        assert state.status == "unavailable"
        assert state.enabled is True
        assert state.artifacts_available is False
        assert state.reason == "missing_manifest"
        assert state.manifest_path == model_dir / "manifest.json"
        assert state.model_paths == {
            60: model_dir / "model_60m.joblib",
            120: model_dir / "model_120m.joblib",
        }

    def test_is_ml_available_false_when_model_dir_missing(self, monkeypatch, tmp_path):
        empty_dir = tmp_path / "empty_models"
        empty_dir.mkdir()
        monkeypatch.setenv("BGMON_ML_ENABLED", "true")
        monkeypatch.setenv("BGMON_ML_MODEL_PATH", str(empty_dir))
        assert Config.is_ml_available() is False

    def test_is_ml_available_idempotent(self, monkeypatch, tmp_path):
        empty_dir = tmp_path / "no_models"
        empty_dir.mkdir()
        monkeypatch.setenv("BGMON_ML_ENABLED", "true")
        monkeypatch.setenv("BGMON_ML_MODEL_PATH", str(empty_dir))

        first = Config.is_ml_available()
        second = Config.is_ml_available()
        assert first is False
        assert second is False

    def test_model_dir_convention(self):
        model_dir = Config.model_dir()
        assert os.path.isabs(model_dir)
        assert model_dir.endswith("ml_models/bg_prediction_v1")
