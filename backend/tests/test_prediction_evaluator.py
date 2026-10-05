"""Tests for retrospective prediction evaluation support — plan task 6."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from bgmon_api.config import Config
from bgmon_api.models import GlucoseReading, PredictionPoint, PredictionRun
from bgmon_api.services.prediction_evaluation_types import (
    EvaluationReason,
    EvaluationVerdict,
)
from bgmon_api.services.prediction_evaluator import (
    PredictionRunEvaluationStatus,
    evaluate_saved_predictions,
)


def _base_time(minutes_ago: int) -> datetime:
    """A recent timestamp, safely inside the evaluator's 7-day window.

    Hard-coded dates silently age out of that window and turn these tests
    into "there is nothing to evaluate" assertions.
    """
    return datetime.now(UTC) - timedelta(minutes=minutes_ago)


def _make_run(
    *,
    user_id: int,
    context_end_at: datetime,
    generated_at: datetime,
    horizon_minutes: int,
    model_version: str,
    feature_version: str | None = "f1",
) -> PredictionRun:
    run = PredictionRun()
    run.user_id = user_id
    run.context_end_at = context_end_at
    run.generated_at = generated_at
    run.horizon_minutes = horizon_minutes
    run.model_version = model_version
    run.feature_version = feature_version
    return run


def _make_point(*, run_id: int, timestamp: datetime, predicted_sgv: float) -> PredictionPoint:
    point = PredictionPoint()
    point.run_id = run_id
    point.timestamp = timestamp
    point.predicted_sgv = predicted_sgv
    return point


def _make_reading(*, timestamp: datetime, sgv: int) -> GlucoseReading:
    reading = GlucoseReading()
    reading.timestamp = timestamp
    reading.sgv = sgv
    reading.source = "test"
    return reading


def _seed_run_with_points(
    *,
    db_session,
    user_id: int,
    context_end_at: datetime,
    generated_at: datetime,
    horizon_minutes: int,
    model_version: str,
    point_values: list[tuple[datetime, float]],
) -> PredictionRun:
    run = _make_run(
        user_id=user_id,
        context_end_at=context_end_at,
        generated_at=generated_at,
        horizon_minutes=horizon_minutes,
        model_version=model_version,
    )
    db_session.add(run)
    db_session.flush()
    for timestamp, predicted_sgv in point_values:
        db_session.add(
            _make_point(run_id=run.id, timestamp=timestamp, predicted_sgv=predicted_sgv)
        )
    db_session.commit()
    return run


class TestEvaluateSavedPredictions:
    """Retrospective scoring of stored prediction runs against actual BG rows."""

    def test_completed_run_with_matching_actual_readings(self, db_session, patient_user):
        base = _base_time(180)
        run = _seed_run_with_points(
            db_session=db_session,
            user_id=patient_user.id,
            context_end_at=base,
            generated_at=base,
            horizon_minutes=60,
            model_version="bgpred-v1",
            point_values=[
                (base + timedelta(minutes=5), 110.0),
                (base + timedelta(minutes=10), 120.0),
                (base + timedelta(minutes=15), 130.0),
            ],
        )
        db_session.add_all(
            [
                _make_reading(timestamp=base + timedelta(minutes=5), sgv=100),
                _make_reading(timestamp=base + timedelta(minutes=10), sgv=125),
                _make_reading(timestamp=base + timedelta(minutes=15), sgv=140),
            ]
        )
        db_session.commit()

        report = evaluate_saved_predictions(tolerance_minutes=5)

        assert len(report.run_summaries) == 1
        summary = report.run_summaries[0]
        assert summary.run_id == run.id
        assert summary.status is PredictionRunEvaluationStatus.COMPLETED
        assert summary.matched_points == 3
        assert summary.point_count == 3
        assert summary.mae == pytest.approx((10.0 + 5.0 + 10.0) / 3.0)
        assert len(summary.point_summaries) == 3

    def test_run_with_no_matching_actual_readings_remains_pending(self, db_session, patient_user):
        base = _base_time(150)
        run = _seed_run_with_points(
            db_session=db_session,
            user_id=patient_user.id,
            context_end_at=base,
            generated_at=base,
            horizon_minutes=60,
            model_version="bgpred-v1",
            point_values=[
                (base + timedelta(minutes=5), 100.0),
                (base + timedelta(minutes=10), 105.0),
            ],
        )

        report = evaluate_saved_predictions(tolerance_minutes=5)

        assert len(report.run_summaries) == 1
        summary = report.run_summaries[0]
        assert summary.run_id == run.id
        assert summary.status is PredictionRunEvaluationStatus.PENDING_ACTUALS
        assert summary.matched_points == 0
        assert summary.mae is None
        assert len(summary.point_summaries) == 0

    def test_aggregate_mae_summary_by_horizon_and_model_version(self, db_session, patient_user):
        base = _base_time(120)
        _seed_run_with_points(
            db_session=db_session,
            user_id=patient_user.id,
            context_end_at=base,
            generated_at=base,
            horizon_minutes=60,
            model_version="bgpred-v1",
            point_values=[
                (base + timedelta(minutes=5), 100.0),
                (base + timedelta(minutes=10), 120.0),
            ],
        )
        _seed_run_with_points(
            db_session=db_session,
            user_id=patient_user.id,
            context_end_at=base + timedelta(hours=1),
            generated_at=base + timedelta(hours=1),
            horizon_minutes=60,
            model_version="bgpred-v1",
            point_values=[
                (base + timedelta(hours=1, minutes=5), 140.0),
                (base + timedelta(hours=1, minutes=10), 150.0),
            ],
        )
        _seed_run_with_points(
            db_session=db_session,
            user_id=patient_user.id,
            context_end_at=base + timedelta(hours=2),
            generated_at=base + timedelta(hours=2),
            horizon_minutes=120,
            model_version="bgpred-v2",
            point_values=[
                (base + timedelta(hours=2, minutes=5), 200.0),
            ],
        )
        db_session.add_all(
            [
                _make_reading(timestamp=base + timedelta(minutes=5), sgv=110),
                _make_reading(timestamp=base + timedelta(minutes=10), sgv=110),
                _make_reading(timestamp=base + timedelta(hours=1, minutes=5), sgv=130),
                _make_reading(timestamp=base + timedelta(hours=1, minutes=10), sgv=140),
                _make_reading(timestamp=base + timedelta(hours=2, minutes=5), sgv=190),
            ]
        )
        db_session.commit()

        report = evaluate_saved_predictions(tolerance_minutes=5)

        aggregate_map = {
            (summary.horizon_minutes, summary.model_version): summary
            for summary in report.aggregate_summaries
        }
        assert aggregate_map[(60, "bgpred-v1")].mae == pytest.approx(10.0)
        assert aggregate_map[(60, "bgpred-v1")].matched_points == 4
        assert aggregate_map[(60, "bgpred-v1")].completed_runs == 2
        assert aggregate_map[(120, "bgpred-v2")].mae == pytest.approx(10.0)
        assert aggregate_map[(120, "bgpred-v2")].matched_points == 1

    def test_predictor_evaluate_command_emits_json_summary(self, app, db_session, patient_user):
        base = _base_time(90)
        _seed_run_with_points(
            db_session=db_session,
            user_id=patient_user.id,
            context_end_at=base,
            generated_at=base,
            horizon_minutes=60,
            model_version="bgpred-v1",
            point_values=[
                (base + timedelta(minutes=5), 100.0),
            ],
        )
        db_session.add(_make_reading(timestamp=base + timedelta(minutes=5), sgv=95))
        db_session.commit()

        runner = app.test_cli_runner()
        result = runner.invoke(args=["predictor", "evaluate", "--json-output"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["aggregate_summaries"][0]["horizon_minutes"] == 60
        assert payload["aggregate_summaries"][0]["model_version"] == "bgpred-v1"
        assert payload["aggregate_summaries"][0]["mae"] == pytest.approx(5.0)


class TestPersistenceBaseline:
    """The baseline must be the last value actually known at forecast time."""

    def test_baseline_is_last_reading_at_or_before_context_end(self, db_session, patient_user):
        base = _base_time(200)
        run = _seed_run_with_points(
            db_session=db_session,
            user_id=patient_user.id,
            context_end_at=base,
            generated_at=base,
            horizon_minutes=60,
            model_version="bgpred-v1",
            point_values=[
                (base + timedelta(minutes=10), 130.0),
                (base + timedelta(minutes=20), 135.0),
            ],
        )
        db_session.add_all(
            [
                # Old value, must be ignored: it is before the context end.
                _make_reading(timestamp=base - timedelta(minutes=30), sgv=70),
                # The most recent known value when the forecast was made.
                _make_reading(timestamp=base - timedelta(minutes=5), sgv=100),
                _make_reading(timestamp=base + timedelta(minutes=10), sgv=125),
                _make_reading(timestamp=base + timedelta(minutes=20), sgv=145),
            ]
        )
        db_session.commit()

        report = evaluate_saved_predictions(tolerance_minutes=5)

        summary = report.run_summaries[0]
        assert summary.run_id == run.id
        assert summary.baseline_matched_points == 2
        # |100-125| = 25 and |100-145| = 45
        assert summary.baseline_mae == pytest.approx(35.0)
        for point in summary.point_summaries:
            assert point.baseline_sgv == pytest.approx(100.0)

    def test_quality_compares_model_against_baseline(self, db_session, patient_user):
        base = _base_time(210)
        _seed_run_with_points(
            db_session=db_session,
            user_id=patient_user.id,
            context_end_at=base,
            generated_at=base,
            horizon_minutes=60,
            model_version="bgpred-v1",
            point_values=[
                (base + timedelta(minutes=10), 120.0),
                (base + timedelta(minutes=20), 120.0),
            ],
        )
        db_session.add_all(
            [
                _make_reading(timestamp=base - timedelta(minutes=5), sgv=100),
                _make_reading(timestamp=base + timedelta(minutes=10), sgv=120),
                _make_reading(timestamp=base + timedelta(minutes=20), sgv=120),
            ]
        )
        db_session.commit()

        report = evaluate_saved_predictions(tolerance_minutes=5)

        quality = report.quality_summaries[0]
        # Model predicts the actual value exactly, the baseline is off by 20.
        assert quality.model_mae == pytest.approx(0.0)
        assert quality.baseline_mae == pytest.approx(20.0)
        assert quality.baseline_points == 2
        assert quality.improvement == pytest.approx(100.0)

    def test_no_reading_before_context_end_yields_no_baseline(
        self, db_session, patient_user, monkeypatch
    ):
        # Gates are lowered so the missing baseline is the only failing reason.
        monkeypatch.setattr(Config, "ML_EVAL_MIN_RUNS", 1)
        monkeypatch.setattr(Config, "ML_EVAL_MIN_POINTS", 1)
        base = _base_time(220)
        _seed_run_with_points(
            db_session=db_session,
            user_id=patient_user.id,
            context_end_at=base,
            generated_at=base,
            horizon_minutes=60,
            model_version="bgpred-v1",
            point_values=[(base + timedelta(minutes=10), 120.0)],
        )
        # Only future readings, so nothing was known at forecast time.
        db_session.add(_make_reading(timestamp=base + timedelta(minutes=10), sgv=130))
        db_session.commit()

        report = evaluate_saved_predictions(tolerance_minutes=5)

        quality = report.quality_summaries[0]
        assert quality.baseline_points == 0
        assert quality.baseline_mae is None
        assert quality.improvement is None
        assert quality.verdict is EvaluationVerdict.INSUFFICIENT_DATA
        assert quality.reason is EvaluationReason.NO_BASELINE


class TestCoverageAndVerdict:
    """Coverage and verdict must make weak numbers look weak."""

    def test_coverage_reflects_points_without_actuals(self, db_session, patient_user):
        base = _base_time(240)
        _seed_run_with_points(
            db_session=db_session,
            user_id=patient_user.id,
            context_end_at=base,
            generated_at=base,
            horizon_minutes=60,
            model_version="bgpred-v1",
            point_values=[
                (base + timedelta(minutes=10), 120.0),
                (base + timedelta(minutes=20), 125.0),
                (base + timedelta(minutes=30), 130.0),
                (base + timedelta(minutes=40), 135.0),
            ],
        )
        # Only two of the four future points have an actual value yet.
        db_session.add_all(
            [
                _make_reading(timestamp=base - timedelta(minutes=5), sgv=100),
                _make_reading(timestamp=base + timedelta(minutes=10), sgv=120),
                _make_reading(timestamp=base + timedelta(minutes=20), sgv=125),
            ]
        )
        db_session.commit()

        report = evaluate_saved_predictions(tolerance_minutes=5)

        quality = report.quality_summaries[0]
        assert quality.expected_points == 4
        assert quality.matched_points == 2
        assert quality.coverage == pytest.approx(0.5)
        assert quality.partial_runs == 1
        assert quality.completed_runs == 0

    def test_too_few_runs_is_insufficient_data(self, db_session, patient_user):
        base = _base_time(250)
        _seed_run_with_points(
            db_session=db_session,
            user_id=patient_user.id,
            context_end_at=base,
            generated_at=base,
            horizon_minutes=60,
            model_version="bgpred-v1",
            point_values=[(base + timedelta(minutes=10), 120.0)],
        )
        db_session.add_all(
            [
                _make_reading(timestamp=base - timedelta(minutes=5), sgv=100),
                _make_reading(timestamp=base + timedelta(minutes=10), sgv=120),
            ]
        )
        db_session.commit()

        report = evaluate_saved_predictions(tolerance_minutes=5)

        quality = report.quality_summaries[0]
        assert quality.verdict is EvaluationVerdict.INSUFFICIENT_DATA
        assert quality.reason is EvaluationReason.TOO_FEW_RUNS

    def test_small_sample_is_provisional_and_full_sample_conclusive(
        self, db_session, patient_user, monkeypatch
    ):
        monkeypatch.setattr(Config, "ML_EVAL_MIN_RUNS", 2)
        monkeypatch.setattr(Config, "ML_EVAL_MIN_POINTS", 2)
        base = _base_time(260)
        for index in range(6):
            run_at = base + timedelta(minutes=10 * index)
            _seed_run_with_points(
                db_session=db_session,
                user_id=patient_user.id,
                context_end_at=run_at,
                generated_at=run_at,
                horizon_minutes=60,
                model_version="bgpred-v1",
                point_values=[(run_at + timedelta(minutes=10), 120.0)],
            )
            db_session.add(_make_reading(timestamp=run_at - timedelta(minutes=5), sgv=100))
            db_session.add(_make_reading(timestamp=run_at + timedelta(minutes=10), sgv=120))
        db_session.commit()

        report = evaluate_saved_predictions(tolerance_minutes=5)

        quality = report.quality_summaries[0]
        assert quality.run_count == 6
        assert quality.completed_runs == 6
        assert quality.matched_points == 6
        # 3x the gate is reached, so this is no longer a provisional number.
        assert quality.verdict is EvaluationVerdict.CONCLUSIVE
        assert quality.reason is EvaluationReason.OK

    def test_runs_without_points_report_pending_coverage(
        self, db_session, patient_user
    ):
        base = _base_time(270)
        db_session.add(
            _make_run(
                user_id=patient_user.id,
                context_end_at=base,
                generated_at=base,
                horizon_minutes=60,
                model_version="bgpred-v1",
            )
        )
        db_session.commit()

        report = evaluate_saved_predictions(tolerance_minutes=5)

        quality = report.quality_summaries[0]
        assert quality.run_count == 1
        assert quality.pending_runs == 1
        assert quality.matched_points == 0
        assert quality.model_mae is None
        assert quality.coverage is None
        assert quality.verdict is EvaluationVerdict.INSUFFICIENT_DATA
        assert report.evaluated_runs == 1


class TestVersionComparison:
    """Versions must only be ranked over the window where all were active."""

    def test_comparison_uses_paired_window_only(self, db_session, patient_user):
        base = _base_time(300)
        # One shared reading grid every 15 minutes, so both versions are scored
        # against the same actual values. Only the predictions differ.
        for offset in range(195, -30, -15):
            db_session.add(
                _make_reading(timestamp=base - timedelta(minutes=offset), sgv=100)
            )
        # Old version: long active and still running once the new version is
        # live. Every point lands exactly on a grid reading.
        for offset in (180, 150, 120, 90, 60, 45, 30):
            run_at = base - timedelta(minutes=offset)
            _seed_run_with_points(
                db_session=db_session,
                user_id=patient_user.id,
                context_end_at=run_at,
                generated_at=run_at,
                horizon_minutes=60,
                model_version="bgpred-old",
                point_values=[(run_at + timedelta(minutes=15), 110.0)],
            )
        # New version: only active over the last half hour, and more accurate.
        for offset in (45, 30, 15):
            run_at = base - timedelta(minutes=offset)
            _seed_run_with_points(
                db_session=db_session,
                user_id=patient_user.id,
                context_end_at=run_at,
                generated_at=run_at,
                horizon_minutes=60,
                model_version="bgpred-new",
                point_values=[(run_at + timedelta(minutes=15), 100.0)],
            )
        db_session.commit()

        report = evaluate_saved_predictions(tolerance_minutes=5)

        # The paired window starts with the new version's first run and ends
        # with the old version's last run.
        assert report.paired_window_start == base - timedelta(minutes=45)
        assert report.paired_window_end == base - timedelta(minutes=30)

        by_version = {row.model_version: row for row in report.version_comparisons}
        assert set(by_version) == {"bgpred-old", "bgpred-new"}
        # Only runs inside the shared window count for the comparison: the old
        # version's five earlier runs predate the new version and must not
        # inflate its sample.
        assert by_version["bgpred-old"].run_count == 2
        assert by_version["bgpred-new"].run_count == 2
        # The quality summary still covers the old version's whole history,
        # which is exactly why both views are reported.
        old_quality = next(
            item
            for item in report.quality_summaries
            if item.model_version == "bgpred-old"
        )
        assert old_quality.run_count == 7
        # Inside the window the new version is exact, the old misses by 10.
        assert by_version["bgpred-new"].model_mae == pytest.approx(0.0)
        assert by_version["bgpred-old"].model_mae == pytest.approx(10.0)
        assert by_version["bgpred-new"].rank == 1
        assert by_version["bgpred-old"].rank == 2
        assert by_version["bgpred-old"].delta_to_best == pytest.approx(10.0)

    def test_single_version_is_never_ranked(self, db_session, patient_user):
        base = _base_time(320)
        for index in range(3):
            run_at = base - timedelta(minutes=30 - index * 10)
            _seed_run_with_points(
                db_session=db_session,
                user_id=patient_user.id,
                context_end_at=run_at,
                generated_at=run_at,
                horizon_minutes=60,
                model_version="bgpred-only",
                point_values=[(run_at + timedelta(minutes=10), 120.0)],
            )
            db_session.add(_make_reading(timestamp=run_at - timedelta(minutes=5), sgv=100))
            db_session.add(_make_reading(timestamp=run_at + timedelta(minutes=10), sgv=120))
        db_session.commit()

        report = evaluate_saved_predictions(tolerance_minutes=5)

        # With one version there is nothing to pair, so no ranking is claimed.
        assert report.paired_window_start is None
        assert report.paired_window_end is None
        row = report.version_comparisons[0]
        assert row.model_version == "bgpred-only"
        assert row.rank == 0
        assert row.verdict is EvaluationVerdict.INSUFFICIENT_DATA
        assert row.reason is EvaluationReason.SINGLE_VERSION


class TestChunkedScoring:
    """Runs must be scored exactly once even across pagination boundaries."""

    def test_all_runs_are_scored_across_chunk_boundaries(
        self, db_session, patient_user, monkeypatch
    ):
        monkeypatch.setattr(
            "bgmon_api.services.prediction_evaluator._CHUNK_SIZE", 2
        )
        base = _base_time(400)
        run_count = 7
        for index in range(run_count):
            run_at = base - timedelta(minutes=run_count - index)
            _seed_run_with_points(
                db_session=db_session,
                user_id=patient_user.id,
                context_end_at=run_at,
                generated_at=run_at,
                horizon_minutes=60,
                model_version="bgpred-v1",
                point_values=[(run_at + timedelta(minutes=10), 120.0)],
            )
            db_session.add(_make_reading(timestamp=run_at - timedelta(minutes=5), sgv=100))
            db_session.add(_make_reading(timestamp=run_at + timedelta(minutes=10), sgv=120))
        db_session.commit()

        progress_seen: list[tuple[int, int]] = []
        report = evaluate_saved_predictions(
            tolerance_minutes=5,
            progress=lambda done, total: progress_seen.append((done, total)),
        )

        assert len(report.run_summaries) == run_count
        assert report.evaluated_runs == run_count
        # Keyset pagination must neither skip nor repeat a run across pages.
        seeded_ids = sorted(summary.run_id for summary in report.run_summaries)
        assert len(set(seeded_ids)) == run_count
        expected_ids = sorted(
            row.id
            for row in db_session.query(PredictionRun).all()
        )
        assert seeded_ids == expected_ids
        quality = report.quality_summaries[0]
        assert quality.run_count == run_count
        assert quality.matched_points == run_count
        assert progress_seen[0] == (0, run_count)
        assert progress_seen[-1] == (run_count, run_count)

    def test_job_mode_drops_run_summaries_but_keeps_aggregates(
        self, db_session, patient_user
    ):
        base = _base_time(420)
        _seed_run_with_points(
            db_session=db_session,
            user_id=patient_user.id,
            context_end_at=base,
            generated_at=base,
            horizon_minutes=60,
            model_version="bgpred-v1",
            point_values=[(base + timedelta(minutes=10), 120.0)],
        )
        db_session.add(_make_reading(timestamp=base - timedelta(minutes=5), sgv=100))
        db_session.add(_make_reading(timestamp=base + timedelta(minutes=10), sgv=120))
        db_session.commit()

        report = evaluate_saved_predictions(
            tolerance_minutes=5, keep_run_summaries=False
        )

        assert report.run_summaries == []
        # Aggregates must survive, otherwise the job would report nothing.
        assert report.aggregate_summaries[0].mae == pytest.approx(0.0)
        assert report.aggregate_summaries[0].matched_points == 1
        assert report.quality_summaries[0].baseline_mae == pytest.approx(20.0)
        assert report.evaluated_runs == 1
