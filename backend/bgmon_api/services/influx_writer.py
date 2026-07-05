"""InfluxDB writer in legacy gluroo format."""

import logging
from datetime import datetime

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from bgmon_api.config import Config

logger = logging.getLogger(__name__)


def get_influx_client() -> InfluxDBClient | None:
    """Return a configured InfluxDB client or None if not configured."""
    if not Config.INFLUXDB_URL:
        logger.warning("INFLUXDB_URL not set — skipping InfluxDB writes")
        return None
    return InfluxDBClient(
        url=Config.INFLUXDB_URL,
        token=Config.INFLUXDB_TOKEN,
        org=Config.INFLUXDB_ORG,
    )


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
    client = get_influx_client()
    if client is None:
        return False

    try:
        write_api = client.write_api(write_type=SYNCHRONOUS)

        if glucose_id:
            # Interpret date_string as a nanosecond timestamp (legacy format)
            try:
                ts_ns = int(date_string)
            except ValueError:
                ts_ns = int(
                    datetime.fromisoformat(date_string.replace("Z", "+00:00")).timestamp()
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
                    datetime.fromisoformat(date_string.replace("Z", "+00:00")).timestamp()
                    * 1_000_000_000
                )
            point = (
                Point("glucose")
                .field("sgv", sgv)
                .field("trend", trend)
                .field("direction", direction)
                .time(ts_ns)
            )

        write_api.write(bucket=Config.INFLUXDB_BUCKET, record=point)
        logger.debug("Wrote glucose sgv=%s to InfluxDB", sgv)
        return True

    except Exception as exc:
        logger.error("Failed to write glucose to InfluxDB: %s", exc)
        return False
    finally:
        client.close()
