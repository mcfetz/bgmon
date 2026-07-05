"""InfluxDB v2 reader — Flux queries for dashboard and stats."""

import logging
from typing import Any

from influxdb_client import InfluxDBClient
from influxdb_client.client.query_api import QueryApi

from bgmon_api.config import Config

logger = logging.getLogger(__name__)


def _get_client() -> InfluxDBClient | None:
    if not Config.INFLUXDB_URL:
        return None
    return InfluxDBClient(
        url=Config.INFLUXDB_URL,
        token=Config.INFLUXDB_TOKEN,
        org=Config.INFLUXDB_ORG,
    )


def _range_to_flux(range_key: str) -> str:
    ranges = {
        "today": "-24h",
        "yesterday": "-48h",
        "this_week": "-7d",
        "last_week": "-14d",
    }
    return ranges.get(range_key, "-24h")


def query_glucose_range(start: str, end: str) -> list[dict[str, Any]]:
    """Return glucose readings between start and end ISO-8601 timestamps."""
    client = _get_client()
    if client is None:
        logger.warning("InfluxDB not configured")
        return []

    try:
        query_api: QueryApi = client.query_api()

        flux = f'''from(bucket: "{Config.INFLUXDB_BUCKET}")
          |> range(start: {start}, stop: {end})
          |> filter(fn: (r) => r._measurement == "glucose")
          |> filter(fn: (r) => r._field == "sgv" or r._field == "trend" or r._field == "direction")
          |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")
          |> sort(columns: ["_time"])
          |> limit(n: 500)'''

        tables = query_api.query(flux)
        readings = []
        for table in tables:
            for record in table.records:
                ts = record.get_time()
                readings.append(
                    {
                        "sgv": record.values.get("sgv"),
                        "trend": record.values.get("trend"),
                        "direction": record.values.get("direction"),
                        "timestamp": ts.isoformat() if ts else None,
                    }
                )
        return readings

    except Exception as exc:
        logger.error("InfluxDB range query failed: %s", exc)
        return []
    finally:
        client.close()


def query_glucose_history(range_key: str = "today") -> list[dict[str, Any]]:
    """Return glucose readings for the given time range.

    Returns list of {sgv, trend, direction, timestamp} sorted ascending.
    """
    client = _get_client()
    if client is None:
        logger.warning("InfluxDB not configured")
        return []

    try:
        query_api: QueryApi = client.query_api()
        flux_dur = _range_to_flux(range_key)

        flux = f'''from(bucket: "{Config.INFLUXDB_BUCKET}")
          |> range(start: {flux_dur})
          |> filter(fn: (r) => r._measurement == "glucose")
          |> filter(fn: (r) => r._field == "sgv" or r._field == "trend" or r._field == "direction")
          |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")
          |> sort(columns: ["_time"])
          |> limit(n: 500)'''

        tables = query_api.query(flux)
        readings = []
        for table in tables:
            for record in table.records:
                ts = record.get_time()
                readings.append(
                    {
                        "sgv": record.values.get("sgv"),
                        "trend": record.values.get("trend"),
                        "direction": record.values.get("direction"),
                        "timestamp": ts.isoformat() if ts else None,
                    }
                )
        return readings

    except Exception as exc:
        logger.error("InfluxDB query failed: %s", exc)
        return []
    finally:
        client.close()


def query_current_glucose() -> dict[str, Any] | None:
    """Return the most recent glucose reading."""
    client = _get_client()
    if client is None:
        return None

    try:
        query_api: QueryApi = client.query_api()
        flux = f'''from(bucket: "{Config.INFLUXDB_BUCKET}")
          |> range(start: -2h)
          |> filter(fn: (r) => r._measurement == "glucose")
          |> filter(fn: (r) => r._field == "sgv" or r._field == "trend" or r._field == "direction")
          |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")
          |> sort(columns: ["_time"], desc: true)
          |> limit(n: 1)'''

        tables = query_api.query(flux)
        for table in tables:
            for record in table.records:
                return {
                    "sgv": record.values.get("sgv"),
                    "trend": record.values.get("trend"),
                    "direction": record.values.get("direction"),
                    "timestamp": record.get_time().isoformat() if record.get_time() else None,
                }
        return None
    except Exception as exc:
        logger.error("InfluxDB current query failed: %s", exc)
        return None
    finally:
        client.close()


def query_stats(range_key: str = "today") -> dict[str, Any]:
    """Calculate stats: mean, TIR (70-180), GMI, std dev, readings count."""
    readings = query_glucose_history(range_key)
    values = [r["sgv"] for r in readings if r.get("sgv") is not None]

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
    std_dev = variance**0.5
    gmi = 46.7 + mean / 1.594  # Nathan 2008
    tir_below = sum(1 for v in values if v < 70)
    tir_above = sum(1 for v in values if v > 180)
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
