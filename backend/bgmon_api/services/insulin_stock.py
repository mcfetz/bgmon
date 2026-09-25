"""Insulin stock tracking — estimate daily usage and alert on low stock."""

import logging
from datetime import UTC, datetime, timedelta

from bgmon_api.extensions import db
from bgmon_api.models import (
    GlobalSettings,
    LogEntry,
    LogEntryType,
    User,
    UserRole,
)

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 14
PRIMING_UNITS_PER_INJECTION = 1.0
DEFAULT_LOW_STOCK_DAYS = 14
ALERT_ID = "insulin_low_stock"


def _settings() -> GlobalSettings:
    s = GlobalSettings.query.first()
    if s is None:
        s = GlobalSettings()
        db.session.add(s)
        db.session.commit()
    return s


def _get_patient_id() -> int | None:
    patient = User.query.filter_by(role=UserRole.PATIENT).first()
    return patient.id if patient else None


def estimate_daily_usage(days: int = LOOKBACK_DAYS) -> dict[str, float]:
    """Average daily insulin units and injection count over the window.

    Each injection consumes an extra unit for the priming test, so the
    effective daily usage is `avg_daily_units + avg_daily_injections`.
    """
    patient_id = _get_patient_id()
    start = datetime.now(UTC) - timedelta(days=days)
    per_day: dict[str, list[float]] = {}
    if patient_id is not None:
        entries = (
            LogEntry.query
            .filter(
                LogEntry.user_id == patient_id,
                LogEntry.entry_type == LogEntryType.INSULIN,
                LogEntry.created_at >= start,
            )
            .all()
        )
        for entry in entries:
            ts = entry.created_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            key = ts.astimezone(UTC).date().isoformat()
            per_day.setdefault(key, []).append(float(entry.value))

    daily_units = [sum(values) for values in per_day.values()]
    daily_injections = [len(values) for values in per_day.values()]
    avg_units = sum(daily_units) / days if daily_units else 0.0
    avg_injections = sum(daily_injections) / days if daily_injections else 0.0
    return {
        "lookback_days": days,
        "active_days": len(daily_units),
        "avg_daily_units": round(avg_units, 1),
        "avg_daily_injections": round(avg_injections, 1),
        "usage_per_day": round(avg_units + avg_injections * PRIMING_UNITS_PER_INJECTION, 1),
    }


def days_left(stock: float | None, usage_per_day: float) -> float | None:
    """Days of insulin remaining, or None when stock/usage is unknown."""
    if not stock or usage_per_day <= 0:
        return None
    return round(stock / usage_per_day, 1)


def compute_status() -> dict:
    """Full insulin stock status: usage estimate, days left, low-stock flag."""
    settings = _settings()
    stock = float(settings.insulin_stock) if settings.insulin_stock is not None else None
    low_stock_days = settings.low_stock_days or DEFAULT_LOW_STOCK_DAYS
    usage = estimate_daily_usage()
    remaining = days_left(stock, usage["usage_per_day"])
    return {
        **usage,
        "stock_units": stock,
        "configured": stock is not None,
        "low_stock_days": low_stock_days,
        "days_left": remaining,
        "low_stock": remaining is not None and remaining < low_stock_days,
    }


def evaluate_low_stock() -> dict | None:
    """Log a SmartAlert NOTE when stock is below the configured threshold."""
    status = compute_status()
    if not status["configured"] or not status["low_stock"]:
        return None

    from bgmon_api.services.smart_alerts import _log_alert, _was_alerted

    if _was_alerted(ALERT_ID, _settings()):
        return None

    _log_alert(
        ALERT_ID,
        f"Insulinbestand niedrig — reicht noch ca. {status['days_left']} Tage",
        "Neues Insulin besorgen. Bestand in den Einstellungen aktualisieren.",
        f"Verbrauch ca. {status['usage_per_day']} U/Tag",
    )
    logger.info(
        "Low insulin stock alert logged: %.1f days left (threshold %d)",
        status["days_left"],
        status["low_stock_days"],
    )
    return status
