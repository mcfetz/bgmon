"""Typed result objects for retrospective prediction evaluation."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime
from typing import TypedDict


class PointSummaryDict(TypedDict):
    """JSON-safe point summary payload."""

    timestamp: str
    predicted_sgv: float
    actual_sgv: int
    abs_error: float


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
    point_summaries: list[PointSummaryDict]


class AggregateSummaryDict(TypedDict):
    """JSON-safe aggregate summary payload."""

    horizon_minutes: int
    model_version: str
    run_count: int
    completed_runs: int
    matched_points: int
    mae: float | None


class EvaluationReportDict(TypedDict):
    """JSON-safe report payload."""

    run_summaries: list[RunSummaryDict]
    aggregate_summaries: list[AggregateSummaryDict]


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

    def to_dict(self) -> PointSummaryDict:
        """Return a JSON-safe representation."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "predicted_sgv": self.predicted_sgv,
            "actual_sgv": self.actual_sgv,
            "abs_error": self.abs_error,
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
class EvaluationReport:
    """Complete retrospective evaluation output."""

    run_summaries: list[PredictionRunSummary]
    aggregate_summaries: list[AggregateEvaluationSummary]

    def to_dict(self) -> EvaluationReportDict:
        """Return a JSON-safe representation."""
        return {
            "run_summaries": [summary.to_dict() for summary in self.run_summaries],
            "aggregate_summaries": [summary.to_dict() for summary in self.aggregate_summaries],
        }
