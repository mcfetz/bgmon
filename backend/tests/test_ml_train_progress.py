"""Progress and ETA reporting for the asynchronous ML training job.

Exercises the real ``_run_train`` path — only data collection, model
publishing and the logbook entry are stubbed — and asserts that the
progress fields reach both the job record and the status endpoint.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from bgmon_api.config import Config
from bgmon_api.routes import settings as settings_routes
from tests.test_model_trainer import _build_seed_data


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
def train_env(app, monkeypatch, tmp_path, progress_calls):  # noqa: ARG001
    """Point the job store at tmp_path and stub the slow/irrelevant steps.

    Depends on ``app`` so that ``create_app()`` has run: ``_run_train`` reads
    the module-level ``bgmon_api.app._app`` handle and bails out without it.
    """
    monkeypatch.setattr(Config, "model_dir", classmethod(lambda _cls: str(tmp_path)))
    monkeypatch.setattr(
        "bgmon_api.commands.train_predictor._collect_training_data",
        lambda: _build_seed_data(n_hours=8),
    )
    monkeypatch.setattr(
        "bgmon_api.services.model_publisher.publish_model", MagicMock(return_value=None)
    )
    monkeypatch.setattr(
        "bgmon_api.commands.train_predictor._create_training_log_entry",
        MagicMock(return_value=None),
    )
    return progress_calls


@pytest.fixture
def running_job() -> str:
    job_id = "testjob0001"
    settings_routes._put_job(job_id, {
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
    })
    return job_id


def test_run_train_reports_every_stage(train_env, running_job):
    settings_routes._run_train(running_job)

    stages = [c["stage"] for c in train_env]
    assert stages[0] == "data"
    assert "train" in stages
    assert stages[-2:] == ["publish", "log"]


def test_run_train_reports_per_horizon_progress(train_env, running_job):
    settings_routes._run_train(running_job)

    train_calls = [c for c in train_env if c["stage"] == "train"]
    assert [c["done"] for c in train_calls] == list(range(1, len(Config.ML_HORIZONS) + 1))
    assert all(c["total"] == len(Config.ML_HORIZONS) for c in train_calls)


def test_progress_patch_preserves_existing_fields(train_env, running_job):
    settings_routes._run_train(running_job)

    # Progress patches must never carry a status field, otherwise they would
    # overwrite the running/completed state that _put_job maintains.
    assert all("status" not in c for c in train_env)

    job = settings_routes._get_job(running_job)
    assert job is not None
    assert job["started_at"], "progress updates must not drop started_at"


def test_eta_is_unknown_until_first_horizon_finishes(train_env, running_job):
    settings_routes._run_train(running_job)

    first = train_env[0]
    assert first["stage"] == "data"
    assert first["eta_s"] is None


def test_eta_is_measured_once_a_horizon_completed(train_env, running_job):
    settings_routes._run_train(running_job)

    train_calls = [c for c in train_env if c["stage"] == "train"]
    assert train_calls[0]["eta_s"] is not None
    assert isinstance(train_calls[0]["eta_s"], int)
    assert train_calls[0]["eta_s"] >= 0


def test_elapsed_seconds_increase_monotonically(train_env, running_job):
    settings_routes._run_train(running_job)

    elapsed = [c["elapsed_s"] for c in train_env]
    assert elapsed == sorted(elapsed)
    assert all(e >= 0 for e in elapsed)


@pytest.mark.usefixtures("train_env")
def test_completed_job_records_total_duration(running_job):
    settings_routes._run_train(running_job)

    job = settings_routes._get_job(running_job)
    assert job is not None
    assert job["status"] == "completed"
    # A stubbed run is sub-second, so only presence/type is asserted here.
    assert isinstance(job["duration_s"], int)
    assert job["duration_s"] >= 0
    assert len(job["metrics"]) == len(Config.ML_HORIZONS)
    assert job["stage"] == "done", "completed record must be marked as done"


@pytest.mark.usefixtures("train_env")
def test_completed_job_stays_visible_for_the_next_estimate(running_job):
    """The terminal record replaces the running one, so it must keep ``kind``.

    Otherwise the next training loses both its start estimate and the
    "last training took ..." hint, because the duration lookup filters on kind.
    """
    settings_routes._run_train(running_job)

    job = settings_routes._get_job(running_job)
    assert job is not None
    assert job["kind"] == "train"
    assert settings_routes._last_completed_duration("train") == float(job["duration_s"])


def test_failed_run_keeps_started_at(train_env, running_job, monkeypatch):
    def boom():
        raise RuntimeError("nope")

    monkeypatch.setattr(
        "bgmon_api.commands.train_predictor._collect_training_data", boom
    )
    settings_routes._run_train(running_job)

    job = settings_routes._get_job(running_job)
    assert job is not None
    assert job["status"] == "failed"
    assert job["started_at"]
    assert train_env[-1]["stage"] == "data", "run must fail during the data stage"


@pytest.mark.usefixtures("train_env")
def test_status_endpoint_exposes_progress(client, auth_headers, admin_user, running_job):
    settings_routes._run_train(running_job)

    response = client.get(
        f"/api/settings/ml/train/{running_job}", headers=auth_headers(admin_user)
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "completed"
    assert isinstance(body["duration_s"], int)
    assert body["total"] == len(Config.ML_HORIZONS)
    assert body["stage"] == "done"


def test_status_endpoint_refreshes_frozen_clock_for_running_job(
    client, auth_headers, admin_user, monkeypatch, tmp_path
):
    """A stage without heartbeat must not report a frozen elapsed time."""
    monkeypatch.setattr(Config, "model_dir", classmethod(lambda _cls: str(tmp_path)))
    settings_routes._put_job("running1", {
        "status": "running",
        "started_at": (datetime.now(UTC) - timedelta(seconds=90)).isoformat(),
        "stage": "data",
        "done": 0,
        "total": len(Config.ML_HORIZONS),
        "elapsed_s": 0,
    })

    response = client.get("/api/settings/ml/train/running1", headers=auth_headers(admin_user))
    assert response.status_code == 200
    body = response.get_json()
    assert 88 <= body["elapsed_s"] <= 95


def test_status_endpoint_keeps_final_duration_for_completed_job(
    client, auth_headers, admin_user, monkeypatch, tmp_path
):
    """A completed run must report its measured duration, not a ticking clock."""
    monkeypatch.setattr(Config, "model_dir", classmethod(lambda _cls: str(tmp_path)))
    settings_routes._put_job("done1", {
        "status": "completed",
        "started_at": (datetime.now(UTC) - timedelta(seconds=600)).isoformat(),
        "stage": "done",
        "done": len(Config.ML_HORIZONS),
        "total": len(Config.ML_HORIZONS),
        "duration_s": 600,
    })

    response = client.get("/api/settings/ml/train/done1", headers=auth_headers(admin_user))
    assert response.status_code == 200
    body = response.get_json()
    assert body["duration_s"] == 600
    assert "elapsed_s" not in body


def test_elapsed_since_ignores_unusable_timestamps():
    assert settings_routes._elapsed_since(None) is None
    assert settings_routes._elapsed_since(12345) is None
    assert settings_routes._elapsed_since("not-a-timestamp") is None


def test_elapsed_since_clamps_future_timestamps():
    assert settings_routes._elapsed_since(
        (datetime.now(UTC) + timedelta(seconds=30)).isoformat()
    ) == 0


def test_patch_job_creates_entry_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "model_dir", classmethod(lambda _cls: str(tmp_path)))

    settings_routes._patch_job("fresh", stage="train", done=1, total=3)

    job = settings_routes._get_job("fresh")
    assert job == {"stage": "train", "done": 1, "total": 3}


def test_last_completed_duration_uses_slowest_run(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "model_dir", classmethod(lambda _cls: str(tmp_path)))
    settings_routes._put_job("a", {"kind": "train", "status": "completed", "duration_s": 12.0})
    settings_routes._put_job("b", {"kind": "train", "status": "completed", "duration_s": 40.0})
    settings_routes._put_job("c", {"kind": "train", "status": "running"})

    assert settings_routes._last_completed_duration("train") == 40.0


def test_last_completed_duration_ignores_other_job_kinds(monkeypatch, tmp_path):
    """A slow model training run is no estimate for an evaluation run."""
    monkeypatch.setattr(Config, "model_dir", classmethod(lambda _cls: str(tmp_path)))
    settings_routes._put_job("t", {"kind": "train", "status": "completed", "duration_s": 900.0})
    settings_routes._put_job("e", {"kind": "evaluate", "status": "completed", "duration_s": 3.0})

    assert settings_routes._last_completed_duration("evaluate") == 3.0
    assert settings_routes._last_completed_duration("train") == 900.0


def test_last_completed_duration_none_without_history(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "model_dir", classmethod(lambda _cls: str(tmp_path)))

    assert settings_routes._last_completed_duration("train") is None
    assert settings_routes._last_completed_duration("evaluate") is None
