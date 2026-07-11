"""Tests for retrospective prediction evaluation support — plan task 6."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from bgmon_api.models import GlucoseReading, PredictionPoint, PredictionRun
from bgmon_api.services.prediction_evaluator import (
    PredictionRunEvaluationStatus,
    evaluate_saved_predictions,
)


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
        base = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
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
        base = datetime(2026, 7, 10, 13, 0, tzinfo=UTC)
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
        base = datetime(2026, 7, 10, 14, 0, tzinfo=UTC)
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
        base = datetime(2026, 7, 10, 15, 0, tzinfo=UTC)
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
