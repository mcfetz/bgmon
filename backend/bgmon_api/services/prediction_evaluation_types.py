"""Typed result objects for retrospective prediction evaluation."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from dataclasses import field as dataclasses_field
from datetime import datetime
from typing import TypedDict


class PointSummaryDict(TypedDict):
    """JSON-safe point summary payload."""

    timestamp: str
    predicted_sgv: float
    actual_sgv: int
    abs_error: float
    baseline_sgv: float | None
    baseline_abs_error: float | None


class RunSummaryDict(TypedDict):
    """JSON-safe run summary payload."""

    run_id: int
    user_id: int
    generated_at: str
    context_end_at: str
    horizon_minutes: int
    model_version: str
    feature_version: str | None
    status: str
    point_count: int
    matched_points: int
    mae: float | None
    baseline_matched_points: int
    baseline_mae: float | None
    point_summaries: list[PointSummaryDict]


class AggregateSummaryDict(TypedDict):
    """JSON-safe aggregate summary payload."""

    horizon_minutes: int
    model_version: str
    run_count: int
    completed_runs: int
    matched_points: int
    mae: float | None


class QualitySummaryDict(TypedDict):
    """JSON-safe model-versus-baseline quality payload."""

    horizon_minutes: int
    model_version: str
    run_count: int
    completed_runs: int
    partial_runs: int
    pending_runs: int
    expected_points: int
    matched_points: int
    coverage: float | None
    model_mae: float | None
    baseline_mae: float | None
    baseline_points: int
    improvement: float | None
    first_run_at: str | None
    last_run_at: str | None
    verdict: str
    reason: str


class VersionComparisonDict(TypedDict):
    """JSON-safe paired version comparison payload."""

    horizon_minutes: int
    model_version: str
    run_count: int
    matched_points: int
    model_mae: float | None
    baseline_mae: float | None
    improvement: float | None
    rank: int
    delta_to_best: float | None
    verdict: str
    reason: str


class EvaluationReportDict(TypedDict):
    """JSON-safe report payload."""

    window_start: str | None
    window_end: str | None
    paired_window_start: str | None
    paired_window_end: str | None
    evaluated_runs: int
    quality_summaries: list[QualitySummaryDict]
    version_comparisons: list[VersionComparisonDict]
    run_summaries: list[RunSummaryDict]
    aggregate_summaries: list[AggregateSummaryDict]


class EvaluationVerdict(enum.StrEnum):
    """How much a number may be trusted."""

    INSUFFICIENT_DATA = "insufficient_data"
    PROVISIONAL = "provisional"
    CONCLUSIVE = "conclusive"


class EvaluationReason(enum.StrEnum):
    """Machine-readable explanation for a verdict."""

    OK = ""
    TOO_FEW_RUNS = "too_few_runs"
    TOO_FEW_POINTS = "too_few_points"
    SMALL_SAMPLE = "small_sample"
    NO_BASELINE = "no_baseline"
    SINGLE_VERSION = "single_version"


class PredictionRunEvaluationStatus(enum.StrEnum):
    """Retrospective evaluation status for one persisted run."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    PENDING_ACTUALS = "pending_actuals"


@dataclass(frozen=True, slots=True)
class EvaluatedPointSummary:
    """Observed actual value matched to one prediction point."""

    timestamp: datetime
    predicted_sgv: float
    actual_sgv: int
    abs_error: float
    baseline_sgv: float | None = None
    baseline_abs_error: float | None = None

    def to_dict(self) -> PointSummaryDict:
        """Return a JSON-safe representation."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "predicted_sgv": self.predicted_sgv,
            "actual_sgv": self.actual_sgv,
            "abs_error": self.abs_error,
            "baseline_sgv": self.baseline_sgv,
            "baseline_abs_error": self.baseline_abs_error,
        }


@dataclass(frozen=True, slots=True)
class PredictionRunSummary:
    """Evaluation outcome for one stored prediction run."""

    run_id: int
    user_id: int
    generated_at: datetime
    context_end_at: datetime
    horizon_minutes: int
    model_version: str
    feature_version: str | None
    status: PredictionRunEvaluationStatus
    point_count: int
    matched_points: int
    mae: float | None
    point_summaries: list[EvaluatedPointSummary]
    baseline_matched_points: int = 0
    baseline_mae: float | None = None

    def to_dict(self) -> RunSummaryDict:
        """Return a JSON-safe representation."""
        return {
            "run_id": self.run_id,
            "user_id": self.user_id,
            "generated_at": self.generated_at.isoformat(),
            "context_end_at": self.context_end_at.isoformat(),
            "horizon_minutes": self.horizon_minutes,
            "model_version": self.model_version,
            "feature_version": self.feature_version,
            "status": self.status.value,
            "point_count": self.point_count,
            "matched_points": self.matched_points,
            "mae": self.mae,
            "baseline_matched_points": self.baseline_matched_points,
            "baseline_mae": self.baseline_mae,
            "point_summaries": [point.to_dict() for point in self.point_summaries],
        }


@dataclass(frozen=True, slots=True)
class AggregateEvaluationSummary:
    """Aggregate error metrics grouped by horizon and model version."""

    horizon_minutes: int
    model_version: str
    run_count: int
    completed_runs: int
    matched_points: int
    mae: float | None

    def to_dict(self) -> AggregateSummaryDict:
        """Return a JSON-safe representation."""
        return {
            "horizon_minutes": self.horizon_minutes,
            "model_version": self.model_version,
            "run_count": self.run_count,
            "completed_runs": self.completed_runs,
            "matched_points": self.matched_points,
            "mae": self.mae,
        }


@dataclass(frozen=True, slots=True)
class QualityEvaluationSummary:
    """Model versus persistence baseline for one horizon and model version.

    This is the number that answers "is the forecast worth using": an MAE on
    its own cannot be judged, because a plausible MAE for a 30-minute glucose
    forecast depends entirely on how volatile the period was.
    """

    horizon_minutes: int
    model_version: str
    run_count: int
    completed_runs: int
    partial_runs: int
    pending_runs: int
    expected_points: int
    matched_points: int
    baseline_points: int
    model_mae: float | None
    baseline_mae: float | None
    improvement: float | None
    first_run_at: datetime | None
    last_run_at: datetime | None
    verdict: EvaluationVerdict
    reason: EvaluationReason

    @property
    def coverage(self) -> float | None:
        """Share of predicted points that could be scored against an actual."""
        if not self.expected_points:
            return None
        return self.matched_points / self.expected_points

    def to_dict(self) -> QualitySummaryDict:
        """Return a JSON-safe representation."""
        return {
            "horizon_minutes": self.horizon_minutes,
            "model_version": self.model_version,
            "run_count": self.run_count,
            "completed_runs": self.completed_runs,
            "partial_runs": self.partial_runs,
            "pending_runs": self.pending_runs,
            "expected_points": self.expected_points,
            "matched_points": self.matched_points,
            "coverage": self.coverage,
            "model_mae": self.model_mae,
            "baseline_mae": self.baseline_mae,
            "baseline_points": self.baseline_points,
            "improvement": self.improvement,
            "first_run_at": self.first_run_at.isoformat() if self.first_run_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "verdict": self.verdict.value,
            "reason": self.reason.value,
        }


@dataclass(frozen=True, slots=True)
class VersionComparisonSummary:
    """One model version scored on the shared comparison window.

    Only versions that were both active during the paired window appear here,
    so a two-hour-old model is never ranked against a week of history.
    """

    horizon_minutes: int
    model_version: str
    run_count: int
    matched_points: int
    model_mae: float | None
    baseline_mae: float | None
    improvement: float | None
    rank: int
    delta_to_best: float | None
    verdict: EvaluationVerdict
    reason: EvaluationReason

    def to_dict(self) -> VersionComparisonDict:
        """Return a JSON-safe representation."""
        return {
            "horizon_minutes": self.horizon_minutes,
            "model_version": self.model_version,
            "run_count": self.run_count,
            "matched_points": self.matched_points,
            "model_mae": self.model_mae,
            "baseline_mae": self.baseline_mae,
            "improvement": self.improvement,
            "rank": self.rank,
            "delta_to_best": self.delta_to_best,
            "verdict": self.verdict.value,
            "reason": self.reason.value,
        }


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Complete retrospective evaluation output."""

    run_summaries: list[PredictionRunSummary] = dataclasses_field(default_factory=list)
    aggregate_summaries: list[AggregateEvaluationSummary] = dataclasses_field(default_factory=list)
    quality_summaries: list[QualityEvaluationSummary] = dataclasses_field(default_factory=list)
    version_comparisons: list[VersionComparisonSummary] = dataclasses_field(default_factory=list)
    window_start: datetime | None = None
    window_end: datetime | None = None
    paired_window_start: datetime | None = None
    paired_window_end: datetime | None = None
    evaluated_runs: int = 0

    def to_dict(self) -> EvaluationReportDict:
        """Return a JSON-safe representation."""
        return {
            "window_start": self.window_start.isoformat() if self.window_start else None,
            "window_end": self.window_end.isoformat() if self.window_end else None,
            "paired_window_start": (
                self.paired_window_start.isoformat() if self.paired_window_start else None
            ),
            "paired_window_end": (
                self.paired_window_end.isoformat() if self.paired_window_end else None
            ),
            "evaluated_runs": self.evaluated_runs,
            "quality_summaries": [summary.to_dict() for summary in self.quality_summaries],
            "version_comparisons": [summary.to_dict() for summary in self.version_comparisons],
            "run_summaries": [summary.to_dict() for summary in self.run_summaries],
            "aggregate_summaries": [summary.to_dict() for summary in self.aggregate_summaries],
        }
