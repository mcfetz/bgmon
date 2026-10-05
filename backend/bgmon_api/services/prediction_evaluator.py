"""Retrospective evaluation for persisted prediction runs.

This module is intentionally backend-only and explicit-command driven for v1.
It compares stored ``PredictionPoint`` rows against later ``GlucoseReading``
rows and emits per-run plus aggregate error summaries. It does not affect
runtime dashboard behaviour or scheduler paths.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import selectinload

from bgmon_api.config import Config
from bgmon_api.extensions import db
from bgmon_api.models import GlucoseReading, PredictionPoint, PredictionRun
from bgmon_api.services.prediction_evaluation_types import (
    AggregateEvaluationSummary,
    EvaluatedPointSummary,
    EvaluationReason,
    EvaluationReport,
    EvaluationVerdict,
    PredictionRunEvaluationStatus,
    PredictionRunSummary,
    QualityEvaluationSummary,
    VersionComparisonSummary,
)


@dataclass(frozen=True, slots=True)
class _NormalizedReading:
    """UTC-normalized glucose reading for nearest-neighbour lookup."""

    timestamp: datetime
    sgv: int


# Runs are streamed in chunks so a 30-day window (~50k runs, ~700k points)
# does not have to be held in memory at once.
_CHUNK_SIZE = 500

# A verdict needs three times the gate to count as conclusive; below the gate
# there is no verdict at all rather than a number that looks authoritative.
_CONCLUSIVE_MULTIPLIER = 3


@dataclass(slots=True)
class _Accumulator:
    """Running totals for one (horizon, model_version) group."""

    horizon_minutes: int
    model_version: str
    run_count: int = 0
    completed_runs: int = 0
    partial_runs: int = 0
    pending_runs: int = 0
    expected_points: int = 0
    matched_points: int = 0
    baseline_points: int = 0
    model_abs_error: float = 0.0
    baseline_abs_error: float = 0.0
    first_run_at: datetime | None = None
    last_run_at: datetime | None = None

    def add(self, summary: PredictionRunSummary) -> None:
        """Fold one scored run into the totals."""
        self.run_count += 1
        if summary.status is PredictionRunEvaluationStatus.COMPLETED:
            self.completed_runs += 1
        elif summary.status is PredictionRunEvaluationStatus.PARTIAL:
            self.partial_runs += 1
        else:
            self.pending_runs += 1
        self.expected_points += summary.point_count
        self.matched_points += summary.matched_points
        self.baseline_points += summary.baseline_matched_points
        self.model_abs_error += sum(point.abs_error for point in summary.point_summaries)
        self.baseline_abs_error += sum(
            point.baseline_abs_error
            for point in summary.point_summaries
            if point.baseline_abs_error is not None
        )
        if self.first_run_at is None:
            self.first_run_at = summary.generated_at
        self.last_run_at = summary.generated_at

    def to_quality(self) -> QualityEvaluationSummary:
        """Freeze the totals into a reportable summary with a verdict."""
        model_mae = None if not self.matched_points else self.model_abs_error / self.matched_points
        baseline_mae = (
            None if not self.baseline_points else self.baseline_abs_error / self.baseline_points
        )
        improvement = _improvement(model_mae, baseline_mae)
        verdict, reason = _verdict_for(
            run_count=self.run_count,
            point_count=self.matched_points,
            baseline_points=self.baseline_points,
        )
        return QualityEvaluationSummary(
            horizon_minutes=self.horizon_minutes,
            model_version=self.model_version,
            run_count=self.run_count,
            completed_runs=self.completed_runs,
            partial_runs=self.partial_runs,
            pending_runs=self.pending_runs,
            expected_points=self.expected_points,
            matched_points=self.matched_points,
            baseline_points=self.baseline_points,
            model_mae=model_mae,
            baseline_mae=baseline_mae,
            improvement=improvement,
            first_run_at=self.first_run_at,
            last_run_at=self.last_run_at,
            verdict=verdict,
            reason=reason,
        )


def _improvement(model_mae: float | None, baseline_mae: float | None) -> float | None:
    """Relative MAE gain over the persistence baseline, in percent."""
    if model_mae is None or not baseline_mae:
        return None
    return (baseline_mae - model_mae) / baseline_mae * 100


def _verdict_for(
    *, run_count: int, point_count: int, baseline_points: int
) -> tuple[EvaluationVerdict, EvaluationReason]:
    """Grade how far a number may be trusted, and say why when it may not."""
    min_runs = max(1, Config.ML_EVAL_MIN_RUNS)
    min_points = max(1, Config.ML_EVAL_MIN_POINTS)
    if run_count < min_runs:
        return EvaluationVerdict.INSUFFICIENT_DATA, EvaluationReason.TOO_FEW_RUNS
    if point_count < min_points:
        return EvaluationVerdict.INSUFFICIENT_DATA, EvaluationReason.TOO_FEW_POINTS
    if not baseline_points:
        return EvaluationVerdict.INSUFFICIENT_DATA, EvaluationReason.NO_BASELINE
    conclusive_runs = min_runs * _CONCLUSIVE_MULTIPLIER
    conclusive_points = min_points * _CONCLUSIVE_MULTIPLIER
    if run_count < conclusive_runs or point_count < conclusive_points:
        return EvaluationVerdict.PROVISIONAL, EvaluationReason.SMALL_SAMPLE
    return EvaluationVerdict.CONCLUSIVE, EvaluationReason.OK


def evaluate_saved_predictions(
    *,
    tolerance_minutes: int = 5,
    progress: Callable[[int, int], None] | None = None,
    keep_run_summaries: bool = True,
) -> EvaluationReport:
    """Compare stored predictions with later actual glucose readings.

    Evaluates runs from the last ``Config.ML_EVAL_WINDOW_DAYS`` days (30 by
    default) and reports three things per horizon and model version:

    * model MAE next to the persistence baseline (always-predict-last-value),
      because a bare MAE cannot be judged without knowing what trivially
      achievable error looked like over the same period
    * coverage — how many predicted points could be scored at all, split by
      run status, plus the time span actually covered
    * a verdict per group, so a number backed by 30 runs is not presented
      like one backed by 30,000

    Model versions are additionally compared against each other, but only over
    the window in which *all* of them were active. A version that is two hours
    old otherwise gets ranked against a week of history, which is how a
    323-point MAE ends up looking like an improvement.

    Points are eagerly loaded via ``selectinload`` to avoid N+1 lazy loading on
    the ``run.points`` relationship, in chunks to bound memory.

    Args:
        tolerance_minutes: Allowed absolute timestamp delta between a predicted
            point and the actual reading chosen for scoring.
        progress: optional callback invoked as ``progress(done, total)``.
            Called once with ``(0, total)`` as soon as the run count is known
            but before scoring starts, and then after every scored run. Used by
            the evaluation job to report progress and derive a measured ETA.
            Not called at all when there is nothing to evaluate.
        keep_run_summaries: retain every per-run summary in the report. Off for
            the job, which only needs the aggregates and would otherwise hold
            ~700k point summaries in memory for a 30-day window.
    """
    window_days = max(1, Config.ML_EVAL_WINDOW_DAYS)
    window_end = datetime.now(UTC)
    cutoff = window_end - timedelta(days=window_days)

    spans = _version_spans(cutoff)
    total_runs = sum(count for count, _, _ in spans.values())
    if not total_runs:
        return EvaluationReport(window_start=cutoff, window_end=window_end)

    tolerance = timedelta(minutes=tolerance_minutes)
    bounds = _point_bounds(cutoff)
    if bounds is None:
        # Runs exist but carry no points at all, so nothing can be scored yet.
        pending: dict[tuple[int, str], _Accumulator] = {}
        all_pending: list[PredictionRunSummary] = []
        for chunk in _iter_run_chunks(cutoff):
            for run in chunk:
                summary = _build_pending_summary(run)
                pending.setdefault(
                    (summary.horizon_minutes, summary.model_version),
                    _Accumulator(summary.horizon_minutes, summary.model_version),
                ).add(summary)
                if keep_run_summaries:
                    all_pending.append(summary)
            db.session.expunge_all()
        quality_summaries = [acc.to_quality() for _, acc in sorted(pending.items())]
        return EvaluationReport(
            run_summaries=all_pending,
            aggregate_summaries=[_to_aggregate(item) for item in quality_summaries],
            quality_summaries=quality_summaries,
            window_start=cutoff,
            window_end=window_end,
            evaluated_runs=total_runs,
        )

    earliest, latest = bounds
    readings = _load_readings(earliest=earliest - tolerance, latest=latest + tolerance)
    reading_timestamps = [reading.timestamp for reading in readings]

    # Announce the total before any scoring, so a progress consumer knows the
    # full size of the job up front.
    if progress is not None:
        progress(0, total_runs)

    paired_start, paired_end = _paired_window(spans)
    quality: dict[tuple[int, str], _Accumulator] = {}
    paired: dict[tuple[int, str], _Accumulator] = {}
    all_summaries: list[PredictionRunSummary] = []
    scored = 0

    # Keyset pagination keeps at most _CHUNK_SIZE runs in memory at a time, so
    # a 30-day window does not materialize ~50k runs and ~700k points at once.
    for chunk in _iter_run_chunks(cutoff):
        for run in chunk:
            summary = _evaluate_run(
                run=run,
                readings=readings,
                reading_timestamps=reading_timestamps,
                tolerance=tolerance,
            )
            key = (summary.horizon_minutes, summary.model_version)
            quality.setdefault(key, _Accumulator(*key)).add(summary)
            if _within(summary.generated_at, paired_start, paired_end):
                paired.setdefault(key, _Accumulator(*key)).add(summary)
            if keep_run_summaries:
                all_summaries.append(summary)
            scored += 1
            if progress is not None:
                progress(scored, total_runs)
        # Release the loaded rows before the next page is fetched.
        db.session.expunge_all()

    quality_summaries = [acc.to_quality() for _, acc in sorted(quality.items())]
    # The legacy aggregate is derived from the same totals, so it stays
    # populated even when the per-run summaries are not retained.
    return EvaluationReport(
        run_summaries=all_summaries,
        aggregate_summaries=[_to_aggregate(item) for item in quality_summaries],
        quality_summaries=quality_summaries,
        version_comparisons=_build_version_comparisons(paired, spans),
        window_start=cutoff,
        window_end=window_end,
        paired_window_start=paired_start,
        paired_window_end=paired_end,
        evaluated_runs=scored,
    )


def _to_aggregate(quality: QualityEvaluationSummary) -> AggregateEvaluationSummary:
    """Project a quality summary onto the original aggregate shape."""
    return AggregateEvaluationSummary(
        horizon_minutes=quality.horizon_minutes,
        model_version=quality.model_version,
        run_count=quality.run_count,
        completed_runs=quality.completed_runs,
        matched_points=quality.matched_points,
        mae=quality.model_mae,
    )


def _within(moment: datetime, start: datetime | None, end: datetime | None) -> bool:
    return not (start is not None and moment < start) and not (
        end is not None and moment > end
    )


def _point_bounds(cutoff: datetime) -> tuple[datetime, datetime] | None:
    """Earliest and latest timestamp the scoring window must cover.

    Resolved with a single aggregate query so the readings window can be
    fetched up front, without first loading every run and its points.
    Returns ``None`` when the window contains no prediction points at all.

    The lower bound also accounts for ``context_end_at``: the persistence
    baseline is the last reading known *when the forecast was made*, which can
    predate the first predicted point. Loading only from the first point
    would leave the baseline empty.
    """
    row = (
        db.session.query(
            func.min(PredictionPoint.timestamp),
            func.max(PredictionPoint.timestamp),
            func.min(PredictionRun.context_end_at),
        )
        .join(PredictionRun, PredictionRun.id == PredictionPoint.run_id)
        .filter(PredictionRun.generated_at >= cutoff)
        .first()
    )
    if row is None:
        return None
    first_point, last_point, first_context = row
    if first_point is None or last_point is None:
        return None
    earliest = _normalize_ts(first_point)
    if first_context is not None:
        earliest = min(earliest, _normalize_ts(first_context))
    return earliest, _normalize_ts(last_point)


def _iter_run_chunks(cutoff: datetime) -> Iterator[list[PredictionRun]]:
    """Yield runs inside the window in keyset-paginated chunks.

    Uses ``(generated_at, id)`` as a stable cursor instead of OFFSET, so
    pagination cost stays flat and no run is skipped or repeated. Points are
    eager-loaded per chunk to avoid N+1 queries.
    """
    cursor: tuple[datetime, int] | None = None
    while True:
        query = (
            db.session.query(PredictionRun)
            .filter(PredictionRun.generated_at >= cutoff)
            .options(selectinload(PredictionRun.points))
        )
        if cursor is not None:
            last_generated_at, last_id = cursor
            query = query.filter(
                or_(
                    PredictionRun.generated_at > last_generated_at,
                    and_(
                        PredictionRun.generated_at == last_generated_at,
                        PredictionRun.id > last_id,
                    ),
                )
            )
        chunk = (
            query.order_by(PredictionRun.generated_at.asc(), PredictionRun.id.asc())
            .limit(_CHUNK_SIZE)
            .all()
        )
        if not chunk:
            return
        last = chunk[-1]
        # Capture the cursor while the objects are still attached; the caller
        # expunges each chunk after consuming it.
        cursor = (_normalize_ts(last.generated_at), last.id)
        yield chunk


def _version_spans(cutoff: datetime) -> dict[str, tuple[int, datetime, datetime]]:
    """Run count plus first/last generation time per model version."""
    rows = (
        db.session.query(
            PredictionRun.model_version,
            func.count(PredictionRun.id),
            func.min(PredictionRun.generated_at),
            func.max(PredictionRun.generated_at),
        )
        .filter(PredictionRun.generated_at >= cutoff)
        .group_by(PredictionRun.model_version)
        .all()
    )
    return {
        version: (int(count), _normalize_ts(first), _normalize_ts(last))
        for version, count, first, last in rows
    }


def _paired_window(
    spans: dict[str, tuple[int, datetime, datetime]]
) -> tuple[datetime | None, datetime | None]:
    """The window in which every present model version was active.

    Returns ``(None, None)`` when only one version exists, since there is
    nothing to pair it against.
    """
    if len(spans) < 2:
        return None, None
    return (
        max(span[1] for span in spans.values()),
        min(span[2] for span in spans.values()),
    )


def _build_version_comparisons(
    paired: dict[tuple[int, str], _Accumulator],
    spans: dict[str, tuple[int, datetime, datetime]],
) -> list[VersionComparisonSummary]:
    """Rank model versions by MAE over the shared window, per horizon.

    Ranks are only assigned where the data supports them; a version without
    enough runs keeps ``rank`` 0 so a two-hour-old model cannot win a ranking
    it did not earn.
    """
    comparisons: list[VersionComparisonSummary] = []
    single_version = len(spans) < 2
    horizons = sorted({horizon for horizon, _ in paired})

    for horizon in horizons:
        rows = [
            (version, accumulator)
            for (h, version), accumulator in paired.items()
            if h == horizon
        ]
        if not rows:
            continue
        ranked = sorted(
            (row for row in rows if row[1].matched_points),
            key=lambda row: (row[1].model_abs_error / row[1].matched_points),
        )
        best_mae = (
            ranked[0][1].model_abs_error / ranked[0][1].matched_points if ranked else None
        )
        rank_of = {version: idx + 1 for idx, (version, _) in enumerate(ranked)}

        for version, accumulator in sorted(rows):
            verdict, reason = _verdict_for(
                run_count=accumulator.run_count,
                point_count=accumulator.matched_points,
                baseline_points=accumulator.baseline_points,
            )
            if single_version:
                verdict = EvaluationVerdict.INSUFFICIENT_DATA
                reason = EvaluationReason.SINGLE_VERSION
                # Nothing to compare against, so no rank may be handed out.
                rank = 0
            else:
                rank = rank_of.get(version, 0)
            model_mae = (
                None
                if not accumulator.matched_points
                else accumulator.model_abs_error / accumulator.matched_points
            )
            baseline_mae = (
                None
                if not accumulator.baseline_points
                else accumulator.baseline_abs_error / accumulator.baseline_points
            )
            delta = None
            # A perfect forecast scores 0.0, so the best MAE must be compared
            # against None explicitly rather than by truthiness.
            if model_mae is not None and best_mae is not None:
                delta = model_mae - best_mae
            comparisons.append(
                VersionComparisonSummary(
                    horizon_minutes=horizon,
                    model_version=version,
                    run_count=accumulator.run_count,
                    matched_points=accumulator.matched_points,
                    model_mae=model_mae,
                    baseline_mae=baseline_mae,
                    improvement=_improvement(model_mae, baseline_mae),
                    rank=rank,
                    delta_to_best=delta,
                    verdict=verdict,
                    reason=reason,
                )
            )
    return comparisons


def _evaluate_run(
    *,
    run: PredictionRun,
    readings: list[_NormalizedReading],
    reading_timestamps: list[datetime],
    tolerance: timedelta,
) -> PredictionRunSummary:
    # The persistence baseline: the last value that was actually known when
    # this forecast was made. Identical to the training baseline, so the two
    # numbers mean the same thing.
    baseline = _last_reading_at_or_before(
        moment=_normalize_ts(run.context_end_at),
        readings=readings,
        reading_timestamps=reading_timestamps,
    )
    baseline_sgv = float(baseline.sgv) if baseline is not None else None

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
        baseline_abs_error = (
            None
            if baseline_sgv is None
            else abs(baseline_sgv - float(matched.sgv))
        )
        point_summaries.append(
            EvaluatedPointSummary(
                timestamp=_normalize_ts(point.timestamp),
                predicted_sgv=float(point.predicted_sgv),
                actual_sgv=matched.sgv,
                abs_error=abs(float(point.predicted_sgv) - float(matched.sgv)),
                baseline_sgv=baseline_sgv,
                baseline_abs_error=baseline_abs_error,
            )
        )

    point_count = len(run.points)
    matched_points = len(point_summaries)
    mae = (
        None
        if matched_points == 0
        else sum(point.abs_error for point in point_summaries) / matched_points
    )
    baseline_errors = [
        point.baseline_abs_error
        for point in point_summaries
        if point.baseline_abs_error is not None
    ]
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
        baseline_matched_points=len(baseline_errors),
        baseline_mae=(sum(baseline_errors) / len(baseline_errors) if baseline_errors else None),
    )


def _last_reading_at_or_before(
    *,
    moment: datetime,
    readings: list[_NormalizedReading],
    reading_timestamps: list[datetime],
) -> _NormalizedReading | None:
    """The most recent reading at or before ``moment``, if any."""
    if not readings:
        return None
    index = bisect_right(reading_timestamps, moment)
    if index == 0:
        return None
    return readings[index - 1]


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
