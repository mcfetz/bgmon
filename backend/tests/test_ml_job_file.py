"""Regression tests for concurrent access to the shared ML job file.

Symptom these guard against: an evaluation or training run that disappears
mid-run, which the client sees as a 404 on the job id it is still polling.

Two independent defects produced that:

* non-atomic writes — ``open(path, "w")`` truncates before writing, so a poll
  landing in that window parsed an empty file and reported "no jobs"
* lost updates — two read-modify-write cycles interleaving, where the second
  one writes back a snapshot taken before the first one's write, deleting the
  other job's record entirely
"""

from __future__ import annotations

import json
import threading

import pytest

from bgmon_api.routes import settings as settings_routes


@pytest.fixture
def job_file(monkeypatch, tmp_path):
    """Point the job file at a tmp dir and give it a pre-existing record."""
    monkeypatch.setattr(settings_routes, "_ml_jobs_path", lambda: str(tmp_path / "ml-jobs.json"))
    settings_routes._put_job("history", {"kind": "train", "status": "completed", "duration_s": 5})
    return tmp_path / "ml-jobs.json"


def _is_read_mode(args: tuple, kwargs: dict) -> bool:
    """``open(path)`` in the read path passes no mode at all; default is "r"."""
    mode = args[0] if args else kwargs.get("mode", "r")
    return "w" not in mode and "a" not in mode and "+" not in mode


def test_partial_file_is_never_visible(job_file, monkeypatch):
    """A reader must not observe the truncate-before-write window."""
    settings_routes._put_job("live", {"kind": "evaluate", "status": "running"})
    observed: list[object] = []
    real_open = open
    stop = threading.Event()

    def watching_open(path, *args, **kwargs):
        # Only the job file, and only for reading.
        if str(path) == str(job_file) and _is_read_mode(args, kwargs):
            stop.wait(0.001)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", watching_open)

    def reader():
        while not stop.is_set():
            jobs = settings_routes._load_jobs()
            observed.append(jobs.get("live"))

    t = threading.Thread(target=reader)
    t.start()
    try:
        for _ in range(200):
            settings_routes._patch_job("live", done=7)
    finally:
        stop.set()
        t.join()

    assert observed, "reader thread never ran"
    # Every single read saw the full record; a torn read would show up as None.
    assert all(o is not None for o in observed)
    assert settings_routes._get_job("live") is not None


def test_concurrent_writers_do_not_drop_each_others_records(job_file):  # noqa: ARG001
    """Interleaved read-modify-write cycles must not lose a job record."""
    errors: list[BaseException] = []

    def writer(job_id: str, rounds: int):
        try:
            for _ in range(rounds):
                settings_routes._patch_job(job_id, status="running")
        except BaseException as exc:  # noqa: BLE001 - reported below
            errors.append(exc)

    threads = [
        threading.Thread(target=writer, args=("evaluate-1", 150)),
        threading.Thread(target=writer, args=("train-1", 150)),
        threading.Thread(target=writer, args=("evaluate-2", 150)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"writer raised: {errors}"
    for job_id in ("evaluate-1", "train-1", "evaluate-2", "history"):
        assert settings_routes._get_job(job_id) is not None, f"{job_id} was dropped"


def test_reader_never_sees_a_missing_job_while_it_is_patched(job_file):  # noqa: ARG001
    """The polling pattern: a fixed job id that must stay resolvable."""
    settings_routes._put_job("poll-me", {"kind": "evaluate", "status": "running"})
    stop = threading.Event()
    misses: list[int] = []

    def reader():
        i = 0
        while not stop.is_set():
            if settings_routes._resolve_job("poll-me") is None:
                misses.append(i)
            i += 1

    t = threading.Thread(target=reader)
    t.start()
    try:
        for done in range(1, 250):
            settings_routes._patch_job("poll-me", done=done, total=249)
    finally:
        stop.set()
        t.join()

    assert not misses, f"poll resolved to None {len(misses)} times"


def test_patch_keeps_unrelated_fields_and_history(job_file):  # noqa: ARG001
    settings_routes._patch_job("history", stage="done", done=3, total=3)

    job = settings_routes._get_job("history")
    assert job == {
        "kind": "train",
        "status": "completed",
        "duration_s": 5,
        "stage": "done",
        "done": 3,
        "total": 3,
    }


def test_corrupt_file_is_reported_instead_of_read_as_no_jobs(job_file):  # noqa: ARG001
    """Returning {} would report a phantom 404 and then erase the history."""
    job_file.write_text("{not json")

    with pytest.raises(ValueError):
        settings_routes._load_jobs()

    # The corrupt file is left alone instead of being silently overwritten.
    assert job_file.read_text() == "{not json"


def test_torn_read_is_retried_once(job_file, monkeypatch):
    """One bad read from a concurrent legacy writer must not surface."""
    import io

    real_open = open
    calls = {"n": 0}

    def torn_open(path, *args, **kwargs):
        if str(path) == str(job_file) and _is_read_mode(args, kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                # Half a JSON document, like the old truncate-then-write.
                return io.StringIO('{"a": {"stat')
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", torn_open)
    settings_routes._put_job("history", {"kind": "train", "status": "completed", "duration_s": 5})

    assert calls["n"] >= 2, "expected a retry after the torn read"
    assert settings_routes._get_job("history")["duration_s"] == 5


def test_saved_file_is_valid_json_after_a_failed_write(job_file, monkeypatch):
    """A write that explodes must not leave a truncated file behind."""
    settings_routes._put_job("keep", {"kind": "train", "status": "completed"})

    def exploding_dump(_jobs, _stream):
        raise OSError("disk full")

    monkeypatch.setattr(json, "dump", exploding_dump)

    with pytest.raises(OSError):
        settings_routes._save_jobs({"broken": {"status": "running"}})

    assert json.loads(job_file.read_text())["keep"]["status"] == "completed"
    # No temp file left behind next to the job file.
    leftovers = [p.name for p in job_file.parent.iterdir() if p.name.startswith(".ml-jobs-")]
    assert leftovers == []


def test_aborted_message_names_the_job_kind():
    assert "Training" in settings_routes._mark_aborted({"kind": "train"})["error"]
    assert "Evaluation" in settings_routes._mark_aborted({"kind": "evaluate"})["error"]
