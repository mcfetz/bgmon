from datetime import UTC, datetime, timedelta
from http import HTTPStatus

from bgmon_api.models import (
    MAX_LOG_ENTRY_NOTE_CHARS,
    MAX_LOG_ENTRY_VALUE,
    BasalRateHistory,
    CarbFactorHistory,
    LogEntry,
    LogEntryType,
)


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


def test_create_log_rejects_non_finite_value(client, patient_user, auth_headers):
    response = client.post(
        "/api/log/",
        json={"entry_type": "insulin", "value": "NaN"},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.get_json() == {"error": "invalid value"}


def test_create_log_rejects_oversized_value_and_note(client, patient_user, auth_headers):
    oversized_value = client.post(
        "/api/log/",
        json={"entry_type": "carbs", "value": MAX_LOG_ENTRY_VALUE + 1},
        headers=auth_headers(patient_user),
    )
    oversized_note = client.post(
        "/api/log/",
        json={"entry_type": "note", "value": 0, "notes": "x" * (MAX_LOG_ENTRY_NOTE_CHARS + 1)},
        headers=auth_headers(patient_user),
    )

    assert oversized_value.status_code == HTTPStatus.BAD_REQUEST
    assert oversized_value.get_json() == {"error": "invalid value"}
    assert oversized_note.status_code == HTTPStatus.BAD_REQUEST
    assert oversized_note.get_json() == {"error": "invalid notes"}


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


def test_patient_can_update_own_carb_factor(client, patient_user, auth_headers, db_session):
    response = client.post(
        "/api/log/carb-factor",
        json={"factor": 12.0, "unit": "g/IE"},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.get_json() == {"factor": 12.0, "unit": "g/IE"}

    entry = CarbFactorHistory.query.filter_by(user_id=patient_user.id).one()
    assert entry.factor == 12.0
    assert entry.unit == "g/IE"
    assert entry.changed_by_id == patient_user.id

    note = LogEntry.query.filter_by(
        user_id=patient_user.id, entry_type=LogEntryType.NOTE
    ).one()
    assert note.notes == f"KE-Faktor auf 12.0 g/IE gesetzt. ({patient_user.display_name})"


def test_admin_can_update_patient_carb_factor(
    client, admin_user, patient_user, auth_headers
):
    response = client.post(
        "/api/log/carb-factor",
        json={"factor": 9.5, "unit": "g/IE"},
        headers=auth_headers(admin_user),
    )

    assert response.status_code == HTTPStatus.CREATED

    entry = CarbFactorHistory.query.filter_by(user_id=patient_user.id).one()
    assert entry.factor == 9.5
    assert entry.changed_by_id == admin_user.id


def _create(client, headers, **payload):
    response = client.post("/api/log/", json=payload, headers=headers)
    assert response.status_code == HTTPStatus.CREATED
    return response.get_json()


def test_update_entry_changes_value_and_notes(client, patient_user, auth_headers):
    entry = _create(
        client, auth_headers(patient_user), entry_type="carbs", value=30, notes="Lunch"
    )

    response = client.patch(
        f"/api/log/{entry['id']}",
        json={"value": 45, "notes": "Lunch (nachgetragen)"},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert data["value"] == 45.0
    assert data["notes"] == "Lunch (nachgetragen)"
    assert data["entry_type"] == "carbs"
    assert data["updated_at"] is not None
    assert data["updated_by"] == patient_user.display_name


def test_update_entry_moves_the_timestamp(client, patient_user, auth_headers):
    entry = _create(client, auth_headers(patient_user), entry_type="insulin", value=2.5)
    new_ts = (datetime.now(UTC) - timedelta(minutes=90)).replace(microsecond=0)

    response = client.patch(
        f"/api/log/{entry['id']}",
        json={"timestamp": new_ts.isoformat()},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.OK
    stored = LogEntry.query.get(entry["id"])
    assert stored.created_at.replace(microsecond=0) == new_ts


def test_update_entry_clears_notes(client, patient_user, auth_headers):
    entry = _create(
        client, auth_headers(patient_user), entry_type="carbs", value=12,
        notes="Tippfehler",
    )

    response = client.patch(
        f"/api/log/{entry['id']}",
        json={"notes": ""},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.get_json()["notes"] is None


def test_update_entry_rejects_negative_and_non_finite_values(
    client, patient_user, auth_headers
):
    entry = _create(client, auth_headers(patient_user), entry_type="insulin", value=2.5)

    for bad in (-1, MAX_LOG_ENTRY_VALUE + 1, "abc"):
        response = client.patch(
            f"/api/log/{entry['id']}",
            json={"value": bad},
            headers=auth_headers(patient_user),
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST, bad


def test_update_entry_rejects_oversized_notes(client, patient_user, auth_headers):
    entry = _create(client, auth_headers(patient_user), entry_type="note", value=0, notes="ok")

    response = client.patch(
        f"/api/log/{entry['id']}",
        json={"notes": "x" * (MAX_LOG_ENTRY_NOTE_CHARS + 1)},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_update_entry_rejects_entry_type_change(client, patient_user, auth_headers):
    entry = _create(client, auth_headers(patient_user), entry_type="carbs", value=30)

    response = client.patch(
        f"/api/log/{entry['id']}",
        json={"entry_type": "insulin", "value": 3},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert LogEntry.query.get(entry["id"]).entry_type == LogEntryType.CARBS


def test_update_system_generated_entries_is_rejected(
    client, patient_user, auth_headers, db_session
):
    for entry_type, notes in (
        (LogEntryType.ALARM, "Alarm ausgelöst"),
        (LogEntryType.SUCCESS, "Badge freigeschaltet: Gold-Streak (🥇)"),
        (LogEntryType.NOTE, "SmartAlert:hypo_rebound: Gegenregulation"),
        (LogEntryType.NOTE, "Kompressionstiefwert erkannt — Sensorposition prüfen."),
    ):
        entry = LogEntry(
            user_id=patient_user.id,
            entry_type=entry_type,
            value=0,
            unit="",
            notes=notes,
        )
        db_session.add(entry)
        db_session.commit()

        response = client.patch(
            f"/api/log/{entry.id}",
            json={"notes": "geändert"},
            headers=auth_headers(patient_user),
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST, notes
        assert LogEntry.query.get(entry.id).notes == notes


def test_update_user_note_is_allowed(client, patient_user, auth_headers):
    entry = _create(
        client, auth_headers(patient_user), entry_type="note", value=0,
        notes="Fühlt sich gut",
    )

    response = client.patch(
        f"/api/log/{entry['id']}",
        json={"notes": "Fühlt sich sehr gut"},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.get_json()["notes"] == "Fühlt sich sehr gut"


def test_update_basal_keeps_one_entry_per_day(client, patient_user, auth_headers):
    first = _create(client, auth_headers(patient_user), entry_type="basal", value=20)
    second_day = (datetime.now(UTC) - timedelta(days=1)).replace(microsecond=0)
    second = _create(
        client,
        auth_headers(patient_user),
        entry_type="basal",
        value=18,
        timestamp=second_day.isoformat(),
    )

    response = client.patch(
        f"/api/log/{second['id']}",
        json={"timestamp": datetime.now(UTC).isoformat()},
        headers=auth_headers(patient_user),
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert LogEntry.query.get(first["id"]).value == 20
    assert LogEntry.query.get(second["id"]).created_at.replace(microsecond=0) == second_day


def test_update_missing_entry_returns_404(client, patient_user, auth_headers):
    response = client.patch(
        "/api/log/999999", json={"value": 1}, headers=auth_headers(patient_user)
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_update_entry_requires_authentication(client, patient_user, auth_headers):
    entry = _create(client, auth_headers(patient_user), entry_type="carbs", value=30)

    response = client.patch(f"/api/log/{entry['id']}", json={"value": 20})

    assert response.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN)
