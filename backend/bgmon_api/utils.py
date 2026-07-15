"""Utility exceptions and helpers for bgmon."""

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import wraps
from typing import Any

from bgmon_api.extensions import db


class BGMonError(Exception):
    """Base exception for bgmon."""



class ConfigurationError(BGMonError):
    """Configuration is missing or invalid."""



class ValidationError(BGMonError):
    """User input validation failed."""

    def __init__(self, field: str, reason: str):
        self.field = field
        self.reason = reason
        super().__init__(f"{field}: {reason}")


class DataStoreError(BGMonError):
    """Database or external data store error."""



class NotificationError(BGMonError):
    """Push or Twilio notification failed."""



class AuthenticationError(BGMonError):
    """Authentication failed."""



class LeaderElectionError(BGMonError):
    """Leader election failed."""



@contextmanager
def transactional_session() -> Generator:
    """Context manager for database transactions with automatic commit/rollback.

    Usage:
        with transactional_session():
            user = User(email="test@example.com")
            db.session.add(user)
            # Automatic commit on success, rollback on exception
    """
    try:
        yield db.session
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def transactional(f):
    """Decorator: wraps a Flask route handler in a transaction.

    Commits on success, rolls back on exception. Replaces manual
    db.session.commit() calls inside the handler.

    Usage:
        @settings_bp.route("/thresholds", methods=["POST"])
        @transactional
        def update_thresholds():
            ...
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            result = f(*args, **kwargs)
            db.session.commit()
            return result
        except Exception:
            db.session.rollback()
            raise
    return wrapper


def parse_iso_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-8601 datetime string, handling 'Z' suffix for UTC.

    Returns naive UTC datetime if the string has no timezone offset.
    Returns None if value is None.
    """
    if value is None:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def compute_glucose_stats(
    values: list[float], low: float = 70.0, high: float = 180.0
) -> dict[str, Any]:
    """Compute GMI, TIR, and summary statistics for a list of glucose values.

    Returns a dict with keys:
        mean, tir_percent, tir_below, tir_above, gmi, std_dev, readings, min, max

    When *values* is empty all numeric fields are None and *readings* is 0.
    """
    if not values:
        return {
            "mean": None,
            "tir_percent": None,
            "tir_below": None,
            "tir_above": None,
            "gmi": None,
            "std_dev": None,
            "readings": 0,
            "min": None,
            "max": None,
        }

    n = len(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    std_dev = variance ** 0.5
    gmi = round(3.31 + 0.02392 * mean, 1)  # Nathan 2008: GMI(%) from mg/dL
    tir_below = sum(1 for v in values if v < low)
    tir_above = sum(1 for v in values if v > high)
    tir_in_range = n - tir_below - tir_above

    return {
        "mean": round(mean, 1),
        "tir_percent": round(tir_in_range / n * 100, 1),
        "tir_below": round(tir_below / n * 100, 1),
        "tir_above": round(tir_above / n * 100, 1),
        "gmi": round(gmi, 1),
        "std_dev": round(std_dev, 1),
        "readings": n,
        "min": min(values),
        "max": max(values),
    }
