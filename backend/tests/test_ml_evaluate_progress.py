"""Progress and ETA reporting for the asynchronous prediction evaluation job.

The seeding helpers come from the evaluator's own test module so that these
tests exercise the real scoring path; only the job plumbing is stubbed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from bgmon_api.config import Config
from bgmon_api.routes import settings as settings_routes
from bgmon_api.services.prediction_evaluator import evaluate_saved_predictions
from tests.test_prediction_evaluator import _base_time, _make_reading, _seed_run_with_points


def _seed_runs(db_session, patient_user, count: int, *, minutes_ago: int = 120) -> list[int]:
    """Seed ``count`` runs, each with one point that has a matching reading."""
    ids = []
    for idx in range(count):
        base = _base_time(minutes_ago) + timedelta(minutes=idx)
        run = _seed_run_with_points(
            db_session=db_session,
            user_id=patient_user.id,
            context_end_at=base,
            generated_at=base,
            horizon_minutes=60,
            model_version="bgpred-v1",
            point_values=[(base + timedelta(minutes=5), 110.0)],
        )
        db_session.add(_make_reading(timestamp=base + timedelta(minutes=5), sgv=105))
        db_session.commit()
        ids.append(run.id)
    return ids


@pytest.fixture
def progress_calls(monkeypatch) -> list[dict]:
    """Record every progress patch while still performing the real write."""
    calls: list[dict] = []
    real_patch = settings_routes._patch_job

    def spy(job_id: str, **fields: object) -> None:
        calls.append(dict(fields))
        real_patch(job_id, **fields)

    monkeypatch.setattr(settings_routes, "_patch_job", spy)
    return calls


@pytest.fixture
def eval_env(app, monkeypatch, tmp_path, progress_calls):  # noqa: ARG001
    """Point the job store at tmp_path; the evaluator itself stays real."""
    monkeypatch.setattr(Config, "model_dir", classmethod(lambda _cls: str(tmp_path)))
    return progress_calls


@pytest.fixture
def running_eval_job() -> str:
    job_id = "evaljob0001"
    settings_routes._put_job(job_id, {
        "kind": "evaluate",
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "stage": "starting",
        "done": 0,
        "total": 0,
    })
    return job_id


# ── evaluator level ──────────────────────────────────────────────────────────


def test_evaluator_announces_total_before_scoring(app, db_session, patient_user):
    _seed_runs(db_session, patient_user, 3)
    seen: list[tuple[int, int]] = []

    with app.app_context():
        report = evaluate_saved_predictions(progress=lambda d, t: seen.append((d, t)))

    assert len(report.run_summaries) == 3
    # First call announces the full size, then one call per scored run.
    assert seen[0] == (0, 3)
    assert [d for d, _ in seen[1:]] == [1, 2, 3]
    assert all(t == 3 for _, t in seen)


def test_evaluator_without_progress_stays_silent(app, db_session, patient_user):
    _seed_runs(db_session, patient_user, 2)

    with app.app_context():
        report = evaluate_saved_predictions()

    assert len(report.run_summaries) == 2


@pytest.mark.usefixtures("db_session")
def test_evaluator_reports_nothing_when_there_is_nothing_to_score(app):
    """An empty evaluation must not emit a bogus 0/0 progress step."""
    seen: list[tuple[int, int]] = []

    with app.app_context():
        report = evaluate_saved_predictions(progress=lambda d, t: seen.append((d, t)))

    assert report.run_summaries == []
    assert seen == []


# ── job level ────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("eval_env")
def test_run_evaluate_reports_load_then_score_then_done(
    db_session, patient_user, progress_calls, running_eval_job
):
    _seed_runs(db_session, patient_user, 3)
    settings_routes._run_evaluate(running_eval_job)

    stages = [c["stage"] for c in progress_calls]
    assert stages[0] == "load"
    assert "score" in stages
    assert [c["done"] for c in progress_calls if c["stage"] == "score"] == [0, 1, 2, 3]


@pytest.mark.usefixtures("eval_env")
def test_run_evaluate_payload_carries_quality_and_window(
    db_session, patient_user, running_eval_job
):
    """The job must ship baseline, coverage, verdict and window to the UI."""
    _seed_runs(db_session, patient_user, 2)
    settings_routes._run_evaluate(running_eval_job)

    job = settings_routes._get_job(running_eval_job)
    assert job is not None
    assert job["status"] == "completed"

    quality = job["quality"]
    assert quality, "quality summaries must be returned"
    row = quality[0]
    for field in (
        "coverage",
        "model_mae",
        "baseline_mae",
        "baseline_points",
        "improvement",
        "verdict",
        "reason",
        "expected_points",
        "matched_points",
    ):
        assert field in row, f"missing quality field: {field}"
    assert row["verdict"] in {"insufficient_data", "provisional", "conclusive"}

    assert job["versions"] is not None
    assert job["evaluated_runs"] == 2
    assert job["window_days"] == Config.ML_EVAL_WINDOW_DAYS
    assert job["window_start"] and job["window_end"]
    # Per-run summaries are dropped in job mode to bound memory.
    assert "run_summaries" not in job


@pytest.mark.usefixtures("eval_env")
def test_run_evaluate_completes_with_measured_duration(
    db_session, patient_user, running_eval_job
):
    _seed_runs(db_session, patient_user, 2)
    settings_routes._run_evaluate(running_eval_job)

    job = settings_routes._get_job(running_eval_job)
    assert job is not None
    assert job["kind"] == "evaluate"
    assert job["status"] == "completed"
    assert job["stage"] == "done"
    assert job["done"] == job["total"] == 2
    assert isinstance(job["duration_s"], int)
    assert job["duration_s"] >= 0
    assert job["started_at"]
    assert job["summaries"], "aggregated summaries must still be returned"


@pytest.mark.usefixtures("eval_env")
def test_evaluate_eta_unknown_until_first_run_is_scored(
    db_session, patient_user, progress_calls, running_eval_job
):
    _seed_runs(db_session, patient_user, 3)
    settings_routes._run_evaluate(running_eval_job)

    score_calls = [c for c in progress_calls if c["stage"] == "score"]
    assert score_calls[0]["done"] == 0
    assert score_calls[0]["eta_s"] is None
    assert isinstance(score_calls[1]["eta_s"], int)
    assert score_calls[1]["eta_s"] >= 0


@pytest.mark.usefixtures("eval_env")
def test_evaluate_elapsed_increases_monotonically(
    db_session, patient_user, progress_calls, running_eval_job
):
    _seed_runs(db_session, patient_user, 2)
    settings_routes._run_evaluate(running_eval_job)

    elapsed = [c["elapsed_s"] for c in progress_calls]
    assert elapsed == sorted(elapsed)


@pytest.mark.usefixtures("eval_env")
def test_evaluate_progress_never_overwrites_status(progress_calls, running_eval_job):
    settings_routes._run_evaluate(running_eval_job)

    assert all("status" not in c for c in progress_calls)


@pytest.mark.usefixtures("eval_env")
def test_failed_evaluation_keeps_started_at(progress_calls, running_eval_job, monkeypatch):
    def boom():
        raise RuntimeError("nope")

    monkeypatch.setattr(
        "bgmon_api.services.prediction_evaluator.evaluate_saved_predictions", boom
    )
    settings_routes._run_evaluate(running_eval_job)

    job = settings_routes._get_job(running_eval_job)
    assert job is not None
    assert job["status"] == "failed"
    assert job["started_at"]
    assert progress_calls[0]["stage"] == "load"


@pytest.mark.usefixtures("eval_env")
def test_evaluation_status_endpoint_exposes_progress(
    client, auth_headers, admin_user, db_session, patient_user, running_eval_job
):
    _seed_runs(db_session, patient_user, 2)
    settings_routes._run_evaluate(running_eval_job)

    response = client.get(
        f"/api/settings/ml/evaluate/{running_eval_job}", headers=auth_headers(admin_user)
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "completed"
    assert body["stage"] == "done"
    assert body["total"] == 2
    assert isinstance(body["duration_s"], int)


@pytest.mark.usefixtures("eval_env")
def test_evaluation_status_endpoint_refreshes_frozen_clock(
    client, auth_headers, admin_user
):
    """The load stage has no heartbeat, so the clock must tick on read."""
    job_id = "evaljob0002"
    settings_routes._put_job(job_id, {
        "kind": "evaluate",
        "status": "running",
        "started_at": (datetime.now(UTC) - timedelta(seconds=75)).isoformat(),
        "stage": "load",
        "done": 0,
        "total": 0,
        "elapsed_s": 0,
    })

    response = client.get(f"/api/settings/ml/evaluate/{job_id}", headers=auth_headers(admin_user))
    assert response.status_code == 200
    body = response.get_json()
    assert 73 <= body["elapsed_s"] <= 80


def test_evaluation_start_reports_previous_duration(
    monkeypatch, tmp_path, client, auth_headers, admin_user
):
    monkeypatch.setattr(Config, "model_dir", classmethod(lambda _cls: str(tmp_path)))
    # Stub the worker itself rather than threading.Thread: a real thread would
    # keep querying the test database after the test has torn it down.
    worker = MagicMock()
    monkeypatch.setattr(settings_routes, "_run_evaluate", worker)
    settings_routes._put_job("old", {
        "kind": "evaluate",
        "status": "completed",
        "duration_s": 42.0,
    })

    response = client.post("/api/settings/ml/evaluate", headers=auth_headers(admin_user))

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "running"
    assert body["last_duration_s"] == 42.0
    job = settings_routes._get_job(body["job_id"])
    assert job is not None
    assert job["kind"] == "evaluate"
    assert job["stage"] == "starting"
    assert job["eta_s"] == 42.0
    # The worker was handed the freshly created job id.
    assert worker.call_args is not None
