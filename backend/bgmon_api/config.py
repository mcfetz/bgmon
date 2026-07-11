"""Application configuration loaded from environment variables."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from dotenv import load_dotenv

load_dotenv()

DEFAULT_ML_ARTIFACT_SUBDIR: Final = "ml_models/bg_prediction_v1"
DEFAULT_ML_HORIZONS: Final = "60,120"
ML_MANIFEST_FILENAME: Final = "manifest.json"

MlRuntimeStatus = Literal["disabled", "unavailable", "ready"]


@dataclass(frozen=True, slots=True)
class MlRuntimeState:
    """Resolved runtime state for prediction model artifacts."""

    enabled: bool
    status: MlRuntimeStatus
    reason: str
    model_dir: Path
    manifest_path: Path
    horizons: tuple[int, ...]
    artifacts_available: bool

    @property
    def model_paths(self) -> dict[int, Path]:
        """Return expected model artifact paths keyed by forecast horizon."""
        return {horizon: self.model_dir / f"model_{horizon}m.joblib" for horizon in self.horizons}


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default)).lower()
    return value in {"1", "true", "yes", "on"}


def _parse_int_list(raw: str) -> list[int]:
    return [int(value.strip()) for value in raw.split(",") if value.strip()]


def _get_int_list(name: str, default: str) -> list[int]:
    raw = os.getenv(name, default)
    try:
        return _parse_int_list(raw)
    except ValueError:
        return _parse_int_list(default)


def _default_ml_model_dir() -> Path:
    return Path(__file__).resolve().parent.parent / DEFAULT_ML_ARTIFACT_SUBDIR


def _get_ml_model_path() -> Path:
    env_path = os.getenv("BGMON_ML_MODEL_PATH", "")
    if env_path:
        return Path(env_path).expanduser()
    return _default_ml_model_dir()


class Config:
    """Flask application configuration."""

    _secret = os.getenv("BGMON_SECRET_KEY")
    if not _secret:
        if "pytest" not in sys.modules:
            raise RuntimeError("BGMON_SECRET_KEY must be set in production")
        _secret = "test-secret-key"
    SECRET_KEY = _secret
    _db_url = os.getenv("BGMON_DATABASE_URL")
    if not _db_url:
        if "pytest" not in sys.modules:
            raise RuntimeError("BGMON_DATABASE_URL must be set")
        _db_url = "postgresql://bgmon:bgmon@localhost:5432/bgmon_test"
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_SIZE = 5
    SQLALCHEMY_MAX_OVERFLOW = 10
    SQLALCHEMY_POOL_RECYCLE = 300
    SQLALCHEMY_POOL_PRE_PING = True

    PUBLIC_BASE_URL = os.getenv("BGMON_PUBLIC_BASE_URL", "http://localhost:5000")

    INFLUXDB_URL = os.getenv("BGMON_INFLUXDB_URL", "")
    INFLUXDB_TOKEN = os.getenv("BGMON_INFLUXDB_TOKEN", "")
    INFLUXDB_ORG = os.getenv("BGMON_INFLUXDB_ORG", "familie-heise.de")
    INFLUXDB_BUCKET = os.getenv("BGMON_INFLUXDB_BUCKET", "gluroo")

    LIBRE_EMAIL = os.getenv("BGMON_LIBRE_EMAIL", "")
    LIBRE_PASSWORD = os.getenv("BGMON_LIBRE_PASSWORD", "")
    LIBRE_REGION = os.getenv("BGMON_LIBRE_REGION", "EU2")

    TWILIO_ACCOUNT_SID = os.getenv("BGMON_TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("BGMON_TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER = os.getenv("BGMON_TWILIO_FROM_NUMBER", "")
    TWILIO_NUMBERS = [
        number.strip()
        for number in os.getenv("BGMON_TWILIO_NUMBERS", "").split(",")
        if number.strip()
    ]
    TWILIO_RETRY_COUNT = int(os.getenv("BGMON_TWILIO_RETRY_COUNT", "3"))
    TWILIO_RETRY_DELAY_S = int(os.getenv("BGMON_TWILIO_RETRY_DELAY_S", "90"))

    @classmethod
    def get_twilio_numbers(cls) -> list[str]:
        """Return available Twilio numbers, including legacy single number."""
        numbers = list(cls.TWILIO_NUMBERS)
        if cls.TWILIO_FROM_NUMBER and cls.TWILIO_FROM_NUMBER not in numbers:
            numbers.append(cls.TWILIO_FROM_NUMBER)
        return numbers

    VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
    VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
    VAPID_SUBJECT = os.getenv("VAPID_SUBJECT", "mailto:admin@example.com")

    BOOTSTRAP_ADMIN_EMAIL = os.getenv("BGMON_BOOTSTRAP_ADMIN_EMAIL", "")
    BOOTSTRAP_ADMIN_PASSWORD = os.getenv("BGMON_BOOTSTRAP_ADMIN_PASSWORD", "")

    LEASE_TTL_S = int(os.getenv("BGMON_LEASE_TTL_S", "30"))
    LEADER_RENEW_S = int(os.getenv("BGMON_LEADER_RENEW_S", "10"))
    SCHEDULER_ENABLED = os.getenv("BGMON_DISABLE_SCHEDULER", "").lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }

    ML_ENABLED: bool = _get_bool("BGMON_ML_ENABLED", default=False)
    ML_MODEL_PATH: str = str(_get_ml_model_path())
    ML_HORIZONS: list[int] = _get_int_list("BGMON_ML_HORIZONS", DEFAULT_ML_HORIZONS)

    @classmethod
    def ml_enabled(cls) -> bool:
        """Return ML_ENABLED, re-reading BGMON_ML_ENABLED from env."""
        return _get_bool("BGMON_ML_ENABLED", default=False)

    @classmethod
    def ml_model_path(cls) -> str:
        """Return ML_MODEL_PATH, re-reading BGMON_ML_MODEL_PATH from env."""
        return str(_get_ml_model_path())

    @classmethod
    def ml_horizons(cls) -> list[int]:
        """Return configured forecast horizons from BGMON_ML_HORIZONS env."""
        return _get_int_list("BGMON_ML_HORIZONS", DEFAULT_ML_HORIZONS)

    @classmethod
    def model_dir(cls) -> str:
        """Return the canonical model-artifact directory for prediction v1."""
        return cls.ml_model_path()

    @classmethod
    def ml_runtime_state(cls) -> MlRuntimeState:
        """Return the controlled runtime state for configured model artifacts."""
        enabled = cls.ml_enabled()
        model_dir = Path(cls.ml_model_path())
        horizons = tuple(cls.ml_horizons())
        manifest_path = model_dir / ML_MANIFEST_FILENAME
        if not enabled:
            return MlRuntimeState(
                enabled=False,
                status="disabled",
                reason="ml_disabled",
                model_dir=model_dir,
                manifest_path=manifest_path,
                horizons=horizons,
                artifacts_available=False,
            )
        if not manifest_path.is_file():
            return MlRuntimeState(
                enabled=True,
                status="unavailable",
                reason="missing_manifest",
                model_dir=model_dir,
                manifest_path=manifest_path,
                horizons=horizons,
                artifacts_available=False,
            )
        missing_model_path = any(
            not (model_dir / f"model_{horizon}m.joblib").is_file() for horizon in horizons
        )
        if missing_model_path:
            return MlRuntimeState(
                enabled=True,
                status="unavailable",
                reason="missing_model_artifact",
                model_dir=model_dir,
                manifest_path=manifest_path,
                horizons=horizons,
                artifacts_available=False,
            )
        return MlRuntimeState(
            enabled=True,
            status="ready",
            reason="ready",
            model_dir=model_dir,
            manifest_path=manifest_path,
            horizons=horizons,
            artifacts_available=True,
        )

    @classmethod
    def is_ml_available(cls) -> bool:
        """Return whether ML prediction is enabled and model artifacts are present."""
        return cls.ml_runtime_state().artifacts_available
