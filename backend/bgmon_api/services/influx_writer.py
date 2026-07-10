"""InfluxDB writer in legacy gluroo format."""
import logging
from typing import Any

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from bgmon_api.config import Config
from bgmon_api.utils import parse_iso_datetime

logger = logging.getLogger(__name__)

_influx_client: InfluxDBClient | None = None
_write_api: Any = None


def _ensure_client() -> InfluxDBClient | None:
    global _influx_client, _write_api
    if not Config.INFLUXDB_URL:
        logger.warning("INFLUXDB_URL not set — skipping InfluxDB writes")
        return None
    if _influx_client is None:
        _influx_client = InfluxDBClient(
            url=Config.INFLUXDB_URL,
            token=Config.INFLUXDB_TOKEN,
            org=Config.INFLUXDB_ORG,
        )
        _write_api = _influx_client.write_api(write_type=SYNCHRONOUS)
    return _influx_client


def write_glucose_to_influx(
    sgv: int,
    trend: int,
    direction: str,
    date_string: str,
    glucose_id: str | None = None,
) -> bool:
    """Write one glucose reading to InfluxDB in the legacy gluroo format.

    Legacy format (gluroo-2-influxdb):
      Measurement: glucose
      Fields: _id, sgv, trend, direction
      Timestamp: dateString (ISO-8601 UTC)

    Returns True on success.
    """
    global _write_api
    client = _ensure_client()
    if client is None:
        return False

    try:
        if glucose_id:
            # Interpret date_string as a nanosecond timestamp (legacy format)
            try:
                ts_ns = int(date_string)
            except ValueError:
                ts_ns = int(
                    parse_iso_datetime(date_string).timestamp()  # type: ignore[union-attr]
                    * 1_000_000_000
                )

            point = (
                Point("glucose")
                .tag("_id", glucose_id)
                .field("sgv", sgv)
                .field("trend", trend)
                .field("direction", direction)
                .time(ts_ns)
            )
        else:
            try:
                ts_ns = int(date_string)
            except ValueError:
                ts_ns = int(
                    parse_iso_datetime(date_string).timestamp()  # type: ignore[union-attr]
                    * 1_000_000_000
                )
            point = (
                Point("glucose")
                .field("sgv", sgv)
                .field("trend", trend)
                .field("direction", direction)
                .time(ts_ns)
            )

        _write_api.write(bucket=Config.INFLUXDB_BUCKET, record=point)
        logger.debug("Wrote glucose sgv=%s to InfluxDB", sgv)
        return True

    except Exception as exc:
        logger.error("Failed to write glucose to InfluxDB: %s", exc)
        return False
