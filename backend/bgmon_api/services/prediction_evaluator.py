"""Retrospective evaluation for persisted prediction runs.

This module is intentionally backend-only and explicit-command driven for v1.
It compares stored ``PredictionPoint`` rows against later ``GlucoseReading``
rows and emits per-run plus aggregate error summaries. It does not affect
runtime dashboard behaviour or scheduler paths.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from bgmon_api.extensions import db
from bgmon_api.models import GlucoseReading, PredictionRun
from bgmon_api.services.prediction_evaluation_types import (
    AggregateEvaluationSummary,
    EvaluatedPointSummary,
    EvaluationReport,
    PredictionRunEvaluationStatus,
    PredictionRunSummary,
)


@dataclass(frozen=True, slots=True)
class _NormalizedReading:
    """UTC-normalized glucose reading for nearest-neighbour lookup."""

    timestamp: datetime
    sgv: int


def evaluate_saved_predictions(*, tolerance_minutes: int = 5) -> EvaluationReport:
    """Compare stored predictions with later actual glucose readings.

    Args:
        tolerance_minutes: Allowed absolute timestamp delta between a predicted
            point and the actual reading chosen for scoring.
    """
    runs = (
        db.session.query(PredictionRun)
        .order_by(PredictionRun.generated_at.asc(), PredictionRun.id.asc())
        .all()
    )
    if not runs:
        return EvaluationReport(run_summaries=[], aggregate_summaries=[])

    points = [point for run in runs for point in run.points]
    if not points:
        run_summaries = [_build_pending_summary(run) for run in runs]
        return EvaluationReport(
            run_summaries=run_summaries,
            aggregate_summaries=_build_aggregate_summaries(run_summaries),
        )

    tolerance = timedelta(minutes=tolerance_minutes)
    earliest = min(_normalize_ts(point.timestamp) for point in points) - tolerance
    latest = max(_normalize_ts(point.timestamp) for point in points) + tolerance
    readings = _load_readings(earliest=earliest, latest=latest)
    reading_timestamps = [reading.timestamp for reading in readings]

    run_summaries = [
        _evaluate_run(
            run=run,
            readings=readings,
            reading_timestamps=reading_timestamps,
            tolerance=tolerance,
        )
        for run in runs
    ]
    return EvaluationReport(
        run_summaries=run_summaries,
        aggregate_summaries=_build_aggregate_summaries(run_summaries),
    )


def _evaluate_run(
    *,
    run: PredictionRun,
    readings: list[_NormalizedReading],
    reading_timestamps: list[datetime],
    tolerance: timedelta,
) -> PredictionRunSummary:
    point_summaries: list[EvaluatedPointSummary] = []
    for point in run.points:
        matched = _find_nearest_reading(
            target=_normalize_ts(point.timestamp),
            readings=readings,
            reading_timestamps=reading_timestamps,
            tolerance=tolerance,
        )
        if matched is None:
            continue
        point_summaries.append(
            EvaluatedPointSummary(
                timestamp=_normalize_ts(point.timestamp),
                predicted_sgv=float(point.predicted_sgv),
                actual_sgv=matched.sgv,
                abs_error=abs(float(point.predicted_sgv) - float(matched.sgv)),
            )
        )

    point_count = len(run.points)
    matched_points = len(point_summaries)
    mae = (
        None
        if matched_points == 0
        else sum(point.abs_error for point in point_summaries) / matched_points
    )
    status = _status_for_counts(point_count=point_count, matched_points=matched_points)
    return PredictionRunSummary(
        run_id=run.id,
        user_id=run.user_id,
        generated_at=_normalize_ts(run.generated_at),
        context_end_at=_normalize_ts(run.context_end_at),
        horizon_minutes=run.horizon_minutes,
        model_version=run.model_version,
        feature_version=run.feature_version,
        status=status,
        point_count=point_count,
        matched_points=matched_points,
        mae=mae,
        point_summaries=point_summaries,
    )


def _build_pending_summary(run: PredictionRun) -> PredictionRunSummary:
    return PredictionRunSummary(
        run_id=run.id,
        user_id=run.user_id,
        generated_at=_normalize_ts(run.generated_at),
        context_end_at=_normalize_ts(run.context_end_at),
        horizon_minutes=run.horizon_minutes,
        model_version=run.model_version,
        feature_version=run.feature_version,
        status=PredictionRunEvaluationStatus.PENDING_ACTUALS,
        point_count=0,
        matched_points=0,
        mae=None,
        point_summaries=[],
    )


def _build_aggregate_summaries(
    run_summaries: list[PredictionRunSummary],
) -> list[AggregateEvaluationSummary]:
    grouped: dict[tuple[int, str], list[PredictionRunSummary]] = {}
    for summary in run_summaries:
        key = (summary.horizon_minutes, summary.model_version)
        grouped.setdefault(key, []).append(summary)

    aggregate_summaries: list[AggregateEvaluationSummary] = []
    for (horizon_minutes, model_version), summaries in sorted(grouped.items()):
        matched_points = sum(summary.matched_points for summary in summaries)
        total_error = sum(
            point.abs_error
            for summary in summaries
            for point in summary.point_summaries
        )
        completed_runs = sum(
            summary.status is PredictionRunEvaluationStatus.COMPLETED
            for summary in summaries
        )
        mae = None if matched_points == 0 else total_error / matched_points
        aggregate_summaries.append(
            AggregateEvaluationSummary(
                horizon_minutes=horizon_minutes,
                model_version=model_version,
                run_count=len(summaries),
                completed_runs=completed_runs,
                matched_points=matched_points,
                mae=mae,
            )
        )
    return aggregate_summaries


def _load_readings(*, earliest: datetime, latest: datetime) -> list[_NormalizedReading]:
    glucose_readings = (
        db.session.query(GlucoseReading)
        .filter(GlucoseReading.timestamp >= earliest)
        .filter(GlucoseReading.timestamp <= latest)
        .order_by(GlucoseReading.timestamp.asc())
        .all()
    )
    return [
        _NormalizedReading(timestamp=_normalize_ts(reading.timestamp), sgv=reading.sgv)
        for reading in glucose_readings
    ]


def _find_nearest_reading(
    *,
    target: datetime,
    readings: list[_NormalizedReading],
    reading_timestamps: list[datetime],
    tolerance: timedelta,
) -> _NormalizedReading | None:
    if not readings:
        return None

    index = bisect_left(reading_timestamps, target)
    candidates: list[_NormalizedReading] = []
    if index < len(readings):
        candidates.append(readings[index])
    if index > 0:
        candidates.append(readings[index - 1])
    if not candidates:
        return None

    closest = min(candidates, key=lambda reading: abs(reading.timestamp - target))
    if abs(closest.timestamp - target) > tolerance:
        return None
    return closest


def _status_for_counts(
    *, point_count: int, matched_points: int
) -> PredictionRunEvaluationStatus:
    if matched_points == 0:
        return PredictionRunEvaluationStatus.PENDING_ACTUALS
    if matched_points == point_count:
        return PredictionRunEvaluationStatus.COMPLETED
    return PredictionRunEvaluationStatus.PARTIAL


def _normalize_ts(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
