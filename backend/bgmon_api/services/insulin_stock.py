"""Insulin stock tracking — estimate daily usage and alert on low stock.

Covers both bolus (rapid-acting, entry_type=insulin) and basal
(long-acting, entry_type=basal) insulin.
"""

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

ALERT_IDS = {
    LogEntryType.INSULIN: "insulin_low_stock",
    LogEntryType.BASAL: "basal_low_stock",
}
STOCK_FIELD = {
    LogEntryType.INSULIN: "insulin_stock",
    LogEntryType.BASAL: "basal_stock",
}
TYPE_LABELS = {
    LogEntryType.INSULIN: "Schnellinsulin",
    LogEntryType.BASAL: "Basalinsulin",
}


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


def estimate_daily_usage(
    entry_type: LogEntryType = LogEntryType.INSULIN,
    days: int = LOOKBACK_DAYS,
) -> dict[str, float]:
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
                LogEntry.entry_type == entry_type,
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


def _build_status(
    entry_type: LogEntryType,
    stock: float | None,
    low_stock_days: int,
) -> dict:
    usage = estimate_daily_usage(entry_type=entry_type)
    remaining = days_left(stock, usage["usage_per_day"])
    return {
        **usage,
        "stock_units": stock,
        "configured": stock is not None,
        "low_stock_days": low_stock_days,
        "days_left": remaining,
        "low_stock": remaining is not None and remaining < low_stock_days,
    }


def compute_status() -> dict:
    """Full insulin stock status covering bolus and basal insulin."""
    settings = _settings()
    low_stock_days = settings.low_stock_days or DEFAULT_LOW_STOCK_DAYS

    def _stock(field: str) -> float | None:
        value = getattr(settings, field)
        return float(value) if value is not None else None

    return {
        "low_stock_days": low_stock_days,
        "bolus": _build_status(
            LogEntryType.INSULIN, _stock(STOCK_FIELD[LogEntryType.INSULIN]), low_stock_days
        ),
        "basal": _build_status(
            LogEntryType.BASAL, _stock(STOCK_FIELD[LogEntryType.BASAL]), low_stock_days
        ),
    }


def _evaluate_type(entry_type: LogEntryType, stock: float | None) -> dict | None:
    """Log a SmartAlert NOTE for one insulin type when stock is low."""
    settings = _settings()
    low_stock_days = settings.low_stock_days or DEFAULT_LOW_STOCK_DAYS
    status = _build_status(entry_type, stock, low_stock_days)
    if not status["configured"] or not status["low_stock"]:
        return None

    from bgmon_api.services.smart_alerts import _log_alert, _was_alerted

    if _was_alerted(ALERT_IDS[entry_type], settings):
        return None

    label = TYPE_LABELS[entry_type]
    _log_alert(
        ALERT_IDS[entry_type],
        f"{label}-Bestand niedrig — reicht noch ca. {status['days_left']} Tage",
        "Neues Insulin besorgen. Bestand in den Einstellungen aktualisieren.",
        f"Verbrauch ca. {status['usage_per_day']} U/Tag",
    )
    logger.info(
        "Low %s stock alert logged: %.1f days left (threshold %d)",
        label,
        status["days_left"],
        status["low_stock_days"],
    )
    return status


def evaluate_low_stock() -> dict | None:
    """Log SmartAlert NOTEs for any insulin type whose stock is low."""
    settings = _settings()

    def _stock(field: str) -> float | None:
        value = getattr(settings, field)
        return float(value) if value is not None else None

    bolus = _evaluate_type(LogEntryType.INSULIN, _stock(STOCK_FIELD[LogEntryType.INSULIN]))
    basal = _evaluate_type(LogEntryType.BASAL, _stock(STOCK_FIELD[LogEntryType.BASAL]))
    if bolus is None and basal is None:
        return None
    return {"bolus": bolus, "basal": basal}
