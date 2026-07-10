from datetime import UTC, datetime, timedelta
from http import HTTPStatus

from bgmon_api.models import BasalRateHistory, CarbFactorHistory, LogEntry, LogEntryType


def test_create_carbs_log_entry_success(client, patient_user, auth_headers):
    response = client.post(
        "/api/log/",
        json={"entry_type": "carbs", "value": 30, "notes": "Lunch"},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.CREATED
    data = response.get_json()
    assert data["entry_type"] == LogEntryType.CARBS.value
    assert data["value"] == 30.0
    assert data["unit"] == "g"
    assert data["notes"] == "Lunch"


def test_create_insulin_log_entry_success(client, patient_user, auth_headers):
    response = client.post(
        "/api/log/",
        json={"entry_type": "insulin", "value": 2.5, "notes": "Correction"},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.CREATED
    data = response.get_json()
    assert data["entry_type"] == LogEntryType.INSULIN.value
    assert data["value"] == 2.5
    assert data["unit"] == "U"


def test_create_basal_log_entry_success(client, patient_user, auth_headers):
    basal_timestamp = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)

    response = client.post(
        "/api/log/",
        json={
            "entry_type": "basal",
            "value": 10,
            "timestamp": basal_timestamp.isoformat(),
        },
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.get_json()["entry_type"] == LogEntryType.BASAL.value


def test_create_second_basal_same_day_keeps_single_entry(
    client,
    patient_user,
    auth_headers,
):
    basal_timestamp = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)

    first_response = client.post(
        "/api/log/",
        json={
            "entry_type": "basal",
            "value": 10,
            "timestamp": basal_timestamp.isoformat(),
        },
        headers=auth_headers(patient_user),
    )
    second_response = client.post(
        "/api/log/",
        json={
            "entry_type": "basal",
            "value": 11,
            "timestamp": (basal_timestamp + timedelta(hours=4)).isoformat(),
        },
        headers=auth_headers(patient_user),
    )

    assert first_response.status_code == HTTPStatus.CREATED
    assert second_response.status_code == HTTPStatus.CONFLICT
    assert second_response.get_json() == {"error": "basal already logged today"}
    assert LogEntry.query.filter_by(
        user_id=patient_user.id,
        entry_type=LogEntryType.BASAL,
    ).count() == 1


def test_create_note_entry(client, patient_user, auth_headers):
    response = client.post(
        "/api/log/",
        json={"entry_type": "note", "value": 0, "unit": "", "notes": "Patient feels fine"},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.CREATED
    data = response.get_json()
    assert data["entry_type"] == LogEntryType.NOTE.value
    assert data["notes"] == "Patient feels fine"


def test_list_own_log_entries_returns_entries(client, patient_user, auth_headers):
    client.post(
        "/api/log/",
        json={"entry_type": "carbs", "value": 22, "notes": "Snack"},
        headers=auth_headers(patient_user),
    )

    response = client.get("/api/log/", headers=auth_headers(patient_user))

    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["entry_type"] == LogEntryType.CARBS.value


def test_list_log_entries_with_date_filter(client, patient_user, auth_headers):
    now = datetime.now(UTC)
    day_start = now.strftime("%Y-%m-%dT00:00:00+00:00")
    day_end = (now + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00+00:00")

    client.post("/api/log/", json={"entry_type": "carbs", "value": 15},
                headers=auth_headers(patient_user))
    client.post("/api/log/", json={"entry_type": "carbs", "value": 45},
                headers=auth_headers(patient_user))

    resp = client.get(f"/api/log/?start={day_start}&end={day_end}",
                      headers=auth_headers(patient_user))
    assert resp.status_code == HTTPStatus.OK
    data = resp.get_json()
    assert len(data) >= 1

def test_delete_own_log_entry_success(client, patient_user, auth_headers):
    create_response = client.post(
        "/api/log/",
        json={"entry_type": "carbs", "value": 18, "notes": "Delete me"},
        headers=auth_headers(patient_user),
    )

    entry_id = create_response.get_json()["id"]
    delete_response = client.delete(f"/api/log/{entry_id}", headers=auth_headers(patient_user))

    assert delete_response.status_code == HTTPStatus.OK
    assert delete_response.get_json() == {"deleted": True}


def test_delete_nonexistent_entry_returns_404(client, patient_user, auth_headers):
    response = client.delete("/api/log/999999", headers=auth_headers(patient_user))

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_get_basal_rate_returns_current_rate(client, patient_user, auth_headers, db_session):
    earlier_entry = BasalRateHistory()
    earlier_entry.user_id = patient_user.id
    earlier_entry.rate = 0.8
    earlier_entry.unit = "U/h"
    earlier_entry.changed_by_id = None
    earlier_entry.changed_at = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    latest_entry = BasalRateHistory()
    latest_entry.user_id = patient_user.id
    latest_entry.rate = 1.0
    latest_entry.unit = "U/h"
    latest_entry.changed_by_id = None
    latest_entry.changed_at = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)
    db_session.add(earlier_entry)
    db_session.add(latest_entry)
    db_session.commit()

    response = client.get("/api/log/basal-rate", headers=auth_headers(patient_user))

    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert data["current"]["rate"] == 1.0
    assert len(data["history"]) == 2


def test_update_basal_rate_as_non_patient_forbidden(client, patient_user, auth_headers):
    response = client.post(
        "/api/log/basal-rate",
        json={"rate": 1.2, "unit": "U/h"},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.get_json() == {"error": "forbidden"}


def test_get_carb_factor_returns_current_factor(client, patient_user, auth_headers, db_session):
    earlier_entry = CarbFactorHistory()
    earlier_entry.user_id = patient_user.id
    earlier_entry.factor = 9.0
    earlier_entry.unit = "g/IE"
    earlier_entry.changed_by_id = None
    earlier_entry.changed_at = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    latest_entry = CarbFactorHistory()
    latest_entry.user_id = patient_user.id
    latest_entry.factor = 10.5
    latest_entry.unit = "g/IE"
    latest_entry.changed_by_id = None
    latest_entry.changed_at = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)
    db_session.add(earlier_entry)
    db_session.add(latest_entry)
    db_session.commit()

    response = client.get("/api/log/carb-factor", headers=auth_headers(patient_user))

    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert data["current"]["factor"] == 10.5
    assert len(data["history"]) == 2


def test_update_carb_factor_as_non_patient_forbidden(client, patient_user, auth_headers):
    response = client.post(
        "/api/log/carb-factor",
        json={"factor": 12.0, "unit": "g/IE"},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.get_json() == {"error": "forbidden"}
