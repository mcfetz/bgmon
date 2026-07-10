"""LibreLinkUp fetcher using direct HTTP requests."""

import hashlib
import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import requests
from dateutil import parser as date_parser
from sqlalchemy.exc import IntegrityError

from bgmon_api.config import Config
from bgmon_api.extensions import db
from bgmon_api.models import GlucoseReading
from bgmon_api.services.influx_writer import write_glucose_to_influx
from bgmon_api.utils import transactional_session

logger = logging.getLogger(__name__)

_last_fetch_at: datetime | None = None
_last_fetch_status: str = "never"

# Map Libre trend arrow to legacy numeric values
_TREND_MAP = {
    "⬇️": (1, "DoubleDown"),
    "↘️": (2, "SingleDown"),
    "➡️": (4, "Flat"),
    "↗️": (6, "SingleUp"),
    "⬆️": (7, "DoubleUp"),
}


def get_last_fetch_info() -> dict[str, str | None]:
    """Return last fetch timestamp and status."""
    return {
        "last_libre_fetch_at": _last_fetch_at.isoformat() if _last_fetch_at else None,
        "last_libre_fetch_status": _last_fetch_status,
    }


def _login(session: requests.Session) -> tuple[str, str, str] | None:
    """Authenticate with LibreLinkUp and return (token, base_url, account_id_hash)."""
    headers = {
        "Content-type": "application/json",
        "Accept": "application/json",
        "product": "llu.ios",
        "version": "4.7.0",
        "Accept-Language": "de",
        "User-Agent": "Mozilla/5.0",
    }
    login_data = {"email": Config.LIBRE_EMAIL, "password": Config.LIBRE_PASSWORD}

    regions = ["de", "eu2", "eu", "us"]
    for region in regions:
        base_url = f"https://api-{region}.libreview.io"
        try:
            r = session.post(
                f"{base_url}/llu/auth/login",
                json=login_data,
                headers=headers,
                timeout=30,
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("data", {}).get("redirect"):
                    redirect_region = data["data"]["region"]
                    base_url = f"https://api-{redirect_region}.libreview.io"
                    r = session.post(
                        f"{base_url}/llu/auth/login",
                        json=login_data,
                        headers=headers,
                        timeout=30,
                    )
                    data = r.json()

                token = data.get("data", {}).get("authTicket", {}).get("token")
                user_id = data.get("data", {}).get("user", {}).get("id")
                if token and user_id:
                    account_id_hash = hashlib.sha256(user_id.encode()).hexdigest()
                    logger.info("LibreLinkUp authenticated via %s", base_url)
                    return token, base_url, account_id_hash
        except requests.RequestException:
            continue

    return None


def _get_patients(
    session: requests.Session,
    token: str,
    base_url: str,
    account_id_hash: str,
) -> list[dict]:
    """Get list of patients from LibreLinkUp."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-type": "application/json",
        "Accept": "application/json",
        "product": "llu.ios",
        "version": "4.17.0",
        "Accept-Language": "de",
        "User-Agent": "Mozilla/5.0",
        "account-id": account_id_hash,
    }

    try:
        r = session.get(f"{base_url}/llu/connections", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            patients = data.get("data", [])
            if patients:
                return patients
    except requests.RequestException:
        pass

    return []


def _get_latest_sgv(
    session: requests.Session,
    token: str,
    base_url: str,
    account_id_hash: str,
    patient_id: str,
) -> dict | None:
    """Get latest glucose reading for a patient."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-type": "application/json",
        "Accept": "application/json",
        "product": "llu.ios",
        "version": "4.17.0",
        "Accept-Language": "de",
        "User-Agent": "Mozilla/5.0",
        "account-id": account_id_hash,
    }

    try:
        r = session.get(
            f"{base_url}/llu/connections/{patient_id}/graph",
            headers=headers,
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            graph_data = data.get("data", {})
            connection = graph_data.get("connection", {})
            glucose_measurement = connection.get("glucoseMeasurement", {})
            historical = graph_data.get("graphData", []) or []

            if glucose_measurement:
                value = glucose_measurement.get("ValueInMgPerDl", 0)
                trend_arrow = glucose_measurement.get("TrendArrow", "")
                timestamp_str = glucose_measurement.get("Timestamp", "")
                trend_num, direction = _TREND_MAP.get(trend_arrow, (4, "Flat"))

                return {
                    "sgv": int(value),
                    "trend": trend_num,
                    "direction": direction,
                    "timestamp": timestamp_str,
                    "graphData": historical,
                }
    except requests.RequestException:
        pass

    return None


def _store_historical_data(graph_data: list[dict]) -> int:
    """Write historical glucose readings from graphData to InfluxDB + PostgreSQL.

    Idempotency strategy:
    - Query existing timestamps in the graphData range once (uses the unique
      index on ``glucose_readings.timestamp``).
    - Skip any entry whose timestamp is already present.
    - The unique constraint on ``GlucoseReading.timestamp`` is the ultimate
      safety net — a race between concurrent fetchers is caught and the
      conflicting row is rolled back instead of raising.

    Returns the number of new entries successfully written to PostgreSQL.
    """
    if not graph_data:
        logger.info("Historical: graphData is empty, nothing to store")
        return 0

    # Parse + validate all entries first so we can compute the query range
    parsed: list[tuple[datetime, int, str]] = []
    for item in graph_data:
        try:
            ts_str = item.get("Timestamp", "")
            value = int(item.get("ValueInMgPerDl", 0))
            if not ts_str or not value:
                continue
            ts = date_parser.parse(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            trend_arrow = item.get("TrendArrow", "")
            parsed.append((ts, value, trend_arrow))
        except (ValueError, KeyError, TypeError):
            continue

    if not parsed:
        logger.warning("Historical: no valid entries after parsing (%d raw items)", len(graph_data))
        return 0

    min_ts = min(p[0] for p in parsed)
    max_ts = max(p[0] for p in parsed)

    # Single ranged query — uses the index on glucose_readings.timestamp
    existing_ts: set[datetime] = {
        row.timestamp
        for row in GlucoseReading.query
        .filter(GlucoseReading.timestamp >= min_ts)
        .filter(GlucoseReading.timestamp <= max_ts)
        .all()
    }

    to_write = [(ts, v, t) for ts, v, t in parsed if ts not in existing_ts]

    if not to_write:
        logger.info(
            "Historical: all %d entries already in DB (range %s → %s)",
            len(parsed), min_ts.isoformat(), max_ts.isoformat(),
        )
        return 0

    logger.info(
        "Historical: %d/%d new entries (range %s → %s, %d already in DB)",
        len(to_write), len(parsed),
        min_ts.isoformat(), max_ts.isoformat(),
        len(parsed) - len(to_write),
    )

    written = 0
    for ts, value, trend_arrow in to_write:
        trend_num, direction = _TREND_MAP.get(trend_arrow, (4, "Flat"))
        date_string = str(int(ts.timestamp() * 1_000_000_000))

        influx_ok = write_glucose_to_influx(
            sgv=value,
            trend=trend_num,
            direction=direction,
            date_string=date_string,
            glucose_id=None,
        )

        if not influx_ok:
            logger.warning("Historical: InfluxDB write failed for ts=%s, continuing with PG", ts)

        try:
            reading = GlucoseReading(
                timestamp=ts,
                sgv=value,
                trend=trend_num,
                direction=direction,
                source="librelinkup",
            )
            with transactional_session():
                db.session.add(reading)
            written += 1
        except IntegrityError:
            db.session.rollback()
            logger.warning("Historical: duplicate timestamp %s (sgv=%s), skipping", ts, value)
        except Exception as exc:
            db.session.rollback()
            logger.error("Historical: failed to write reading at %s: %s", ts, exc)

    logger.info(
        "Historical: wrote %d/%d new entries to InfluxDB + PostgreSQL",
        written, len(to_write),
    )
    return written


def fetch_and_store(fetch_history: bool = False) -> None:
    """Fetch latest glucose from LibreLinkUp and write to InfluxDB.

    When ``fetch_history`` is True, the ~12h of historical 15-min averages
    delivered in ``graphData`` are also persisted (idempotent — duplicates
    are skipped via timestamp lookup and the unique constraint).
    """
    global _last_fetch_at, _last_fetch_status

    if not Config.LIBRE_EMAIL or not Config.LIBRE_PASSWORD:
        logger.warning("Libre credentials not configured — skipping fetch")
        _last_fetch_status = "no_credentials"
        return

    _last_fetch_at = datetime.now(UTC)

    session = requests.Session()
    try:
        result = _login(session)
        if not result:
            logger.error("LibreLinkUp authentication failed")
            _last_fetch_status = "auth_failed"
            return

        token, base_url, account_id_hash = result

        patients = _get_patients(session, token, base_url, account_id_hash)
        if not patients:
            logger.warning("No patients found in LibreLinkUp account")
            _last_fetch_status = "no_patients"
            return

        patient_id = patients[0].get("patientId")
        if not patient_id:
            logger.error("No patientId found")
            _last_fetch_status = "no_patient_id"
            return

        measurement = _get_latest_sgv(session, token, base_url, account_id_hash, patient_id)
        if not measurement:
            logger.error("No glucose measurement found")
            _last_fetch_status = "no_measurement"
            return

        try:
            ts = date_parser.parse(measurement["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=ZoneInfo("Europe/Berlin")).astimezone(UTC)
            date_string = str(int(ts.timestamp() * 1_000_000_000))
        except (ValueError, KeyError):
            ts = datetime.now(UTC)
            date_string = str(int(ts.timestamp() * 1_000_000_000))

        ok = write_glucose_to_influx(
            sgv=measurement["sgv"],
            trend=measurement["trend"],
            direction=measurement["direction"],
            date_string=date_string,
            glucose_id=None,
        )

        if not ok:
            logger.warning("InfluxDB write failed for current reading, continuing with PG")

        try:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            stmt = pg_insert(GlucoseReading).values(
                timestamp=ts,
                sgv=measurement["sgv"],
                trend=measurement["trend"],
                direction=measurement["direction"],
                source="librelinkup",
            ).on_conflict_do_update(
                index_elements=["timestamp"],
                set_={
                    "sgv": measurement["sgv"],
                    "trend": measurement["trend"],
                    "direction": measurement["direction"],
                    "source": "librelinkup",
                },
            )
            db.session.execute(stmt)
            with transactional_session():
                pass  # commit handled by context manager
        except Exception:
            db.session.rollback()
            logger.warning(
                "Failed to upsert current reading at %s (sgv=%s)",
                ts, measurement["sgv"],
            )

        if fetch_history:
            graph_data = measurement.get("graphData", []) or []
            logger.info("Fetched %d historical entries from graphData", len(graph_data))
            historical_written = _store_historical_data(graph_data)
            logger.info("Historical backfill wrote %d new entries", historical_written)

        _last_fetch_status = "ok" if ok else "ok_influx_failed"
        logger.info(
            "Fetched glucose: %s mg/dL, trend=%s, direction=%s, ts=%s",
            measurement["sgv"],
            measurement["trend"],
            measurement["direction"],
            ts,
        )

    except Exception as exc:
        logger.error("LibreLinkUp fetch failed: %s", exc)
        _last_fetch_status = f"error: {exc}"
    finally:
        session.close()

