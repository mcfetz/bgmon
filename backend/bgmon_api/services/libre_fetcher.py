"""LibreLinkUp fetcher using direct HTTP requests."""

import hashlib
import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import requests
from dateutil import parser as date_parser

from bgmon_api.app import db
from bgmon_api.config import Config
from bgmon_api.models import GlucoseReading
from bgmon_api.services.influx_writer import write_glucose_to_influx

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
                }
    except requests.RequestException:
        pass

    return None


def fetch_and_store() -> None:
    """Fetch latest glucose from LibreLinkUp and write to InfluxDB."""
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

        if ok:
            try:
                reading = GlucoseReading(
                    timestamp=ts,
                    sgv=measurement["sgv"],
                    trend=measurement["trend"],
                    direction=measurement["direction"],
                    source="librelinkup",
                )
                db.session.add(reading)
                db.session.commit()
            except Exception:
                db.session.rollback()

        _last_fetch_status = "ok" if ok else "write_failed"
        if ok:
            logger.info(
                "Fetched glucose: %s mg/dL, trend=%s, direction=%s",
                measurement["sgv"],
                measurement["trend"],
                measurement["direction"],
            )

    except Exception as exc:
        logger.error("LibreLinkUp fetch failed: %s", exc)
        _last_fetch_status = f"error: {exc}"
    finally:
        session.close()

