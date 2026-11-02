from __future__ import annotations

from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest

from bgmon_api.models import LogEntry, LogEntryType
from bgmon_api.utils import compute_glucose_stats


def test_current_glucose(client, patient_user, glucose_reading_normal, auth_headers):
    response = client.get(
        "/api/dashboard/current",
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.get_json()["sgv"] == glucose_reading_normal.sgv


def test_current_glucose_empty(client, patient_user, auth_headers):
    response = client.get(
        "/api/dashboard/current",
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.get_json() == {"error": "no data"}


def test_history(client, patient_user, glucose_readings, auth_headers):
    response = client.get(
        "/api/dashboard/history?hours=24",
        headers=auth_headers(patient_user),
    )

    data = response.get_json()

    assert response.status_code == HTTPStatus.OK
    assert isinstance(data, list)
    assert len(data) == len(glucose_readings)
    assert data[0]["sgv"] == glucose_readings[0].sgv
    assert data[-1]["sgv"] == glucose_readings[-1].sgv


def test_history_with_date_range(client, patient_user, glucose_readings, auth_headers):
    start = glucose_readings[5].timestamp.isoformat()
    end = glucose_readings[9].timestamp.isoformat()

    response = client.get(
        "/api/dashboard/history",
        query_string={"start": start, "end": end},
        headers=auth_headers(patient_user),
    )

    data = response.get_json()

    assert response.status_code == HTTPStatus.OK
    assert [item["sgv"] for item in data] == [reading.sgv for reading in glucose_readings[5:10]]


@pytest.mark.usefixtures("thresholds", "global_settings")
def test_stats(client, patient_user, glucose_readings, auth_headers):
    response = client.get(
        "/api/dashboard/stats",
        headers=auth_headers(patient_user),
    )

    data = response.get_json()
    expected = compute_glucose_stats([reading.sgv for reading in glucose_readings])

    assert response.status_code == HTTPStatus.OK
    assert data["mean"] == expected["mean"]
    assert data["tir_percent"] == expected["tir_percent"]
    assert data["gmi"] == expected["gmi"]
    assert data["std_dev"] == expected["std_dev"]


def test_stats_empty(client, patient_user, auth_headers):
    response = client.get(
        "/api/dashboard/stats",
        headers=auth_headers(patient_user),
    )

    data = response.get_json()

    assert response.status_code == HTTPStatus.OK
    assert data["mean"] is None
    assert data["tir_percent"] is None
    assert data["gmi"] is None
    assert data["std_dev"] is None
    assert data["readings"] == 0


def test_thresholds(client, patient_user, thresholds, auth_headers):
    response = client.get(
        "/api/dashboard/thresholds",
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.get_json() == {
        "critical_low": thresholds.critical_low,
        "low": thresholds.low,
        "high": thresholds.high,
        "critical_high": thresholds.critical_high,
        "no_data_after_minutes": thresholds.no_data_after_minutes,
    }


def test_logs(client, db_session, patient_user, observer_user, auth_headers):
    earlier_entry = LogEntry()
    earlier_entry.user_id = patient_user.id
    earlier_entry.entry_type = LogEntryType.CARBS
    earlier_entry.value = 18
    earlier_entry.unit = "g"
    earlier_entry.notes = "Juice"
    earlier_entry.created_at = datetime.now(UTC) - timedelta(hours=2)

    later_entry = LogEntry()
    later_entry.user_id = patient_user.id
    later_entry.entry_type = LogEntryType.NOTE
    later_entry.value = 0
    later_entry.unit = ""
    later_entry.notes = "Felt better"
    later_entry.created_at = datetime.now(UTC) - timedelta(hours=1)

    db_session.add(earlier_entry)
    db_session.add(later_entry)
    db_session.commit()

    response = client.get(
        "/api/dashboard/logs",
        headers=auth_headers(observer_user),
    )

    data = response.get_json()

    assert response.status_code == HTTPStatus.OK
    assert [entry["notes"] for entry in data] == ["Juice", "Felt better"]
    assert [entry["entry_type"] for entry in data] == ["carbs", "note"]


def _add_smart_alert_note(db_session, user_id: int, notes: str) -> None:
    db_session.add(
        LogEntry(
            user_id=user_id,
            entry_type=LogEntryType.NOTE,
            value=0,
            unit="",
            notes=notes,
            created_at=datetime.now(UTC) - timedelta(minutes=5),
        )
    )
    db_session.commit()


def test_smart_alerts_keeps_parentheses_inside_the_recommendation(
    client, db_session, patient_user, global_settings, auth_headers
):
    """Only the trailing "(details)" group is stripped, not the first " (".

    The rebound text contains "(Leber)"; cutting at the first parenthesis
    truncated the recommendation to half a sentence.
    """
    _add_smart_alert_note(
        db_session=db_session,
        user_id=patient_user.id,
        notes=(
            "SmartAlert:hypo_rebound: Gegenregulation nach Unterzuckerung "
            "(+120 mg/dL). Empfehlung: Kein Korrektur-Insulin! Das ist die "
            "körpereigene Gegenregulation (Leber), nicht das Essen. "
            "(von 60 auf 180)"
        ),
    )

    response = client.get("/api/dashboard/smart-alerts", headers=auth_headers(patient_user))

    assert response.status_code == HTTPStatus.OK
    alerts = response.get_json()["alerts"]
    rebound = next(a for a in alerts if a["id"] == "hypo_rebound")
    assert rebound["title"] == "Gegenregulation nach Unterzuckerung (+120 mg/dL)"
    assert "(Leber)" in rebound["recommendation"]
    assert "von 60 auf 180" not in rebound["recommendation"]


def test_smart_alerts_parses_the_stored_note_id(
    client, db_session, patient_user, global_settings, auth_headers
):
    """The id sits directly behind "SmartAlert:", the title after the next ": "."""
    _add_smart_alert_note(
        db_session=db_session,
        user_id=patient_user.id,
        notes=(
            "SmartAlert:insulin_stacking: Mehrere Korrektur-Gaben in 139 Min. "
            "Empfehlung: Warte 41 Min. IOB: 3.3 IE. (2 Korrekturen, 4.0 IE gesamt)"
        ),
    )

    response = client.get("/api/dashboard/smart-alerts", headers=auth_headers(patient_user))

    assert response.status_code == HTTPStatus.OK
    alert = next(a for a in response.get_json()["alerts"] if a["id"] == "insulin_stacking")
    assert alert["title"] == "Mehrere Korrektur-Gaben in 139 Min"
    assert alert["recommendation"] == "Warte 41 Min. IOB: 3.3 IE."
    assert alert["icon"] == "💉"
