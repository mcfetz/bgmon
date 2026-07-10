"""Application configuration loaded from environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default)).lower()
    return value in {"1", "true", "yes", "on"}


class Config:
    """Flask application configuration."""

    _secret = os.getenv("BGMON_SECRET_KEY")
    if not _secret:
        import sys
        if "pytest" not in sys.modules:
            raise RuntimeError("BGMON_SECRET_KEY must be set in production")
        _secret = "test-secret-key"
    SECRET_KEY = _secret
    _db_url = os.getenv("BGMON_DATABASE_URL")
    if not _db_url:
        import sys
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
        n.strip() for n in os.getenv("BGMON_TWILIO_NUMBERS", "").split(",") if n.strip()
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
