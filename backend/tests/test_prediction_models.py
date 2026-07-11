"""Tests for PredictionRun and PredictionPoint persistence models (plan task 2).

These tests use the app fixture which runs db.create_all() on a test DB,
so they depend on the models being registered in models.py and the
migration having been applied (or created via create_all for testing).
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from bgmon_api.models import PredictionPoint, PredictionRun


def _make_run(
    *,
    user_id: int,
    context_end_at: datetime,
    horizon_minutes: int,
    model_version: str,
    feature_version: str | None = None,
) -> PredictionRun:
    run = PredictionRun()
    run.user_id = user_id
    run.context_end_at = context_end_at
    run.horizon_minutes = horizon_minutes
    run.model_version = model_version
    run.feature_version = feature_version
    return run


def _make_point(
    *,
    run_id: int,
    timestamp: datetime,
    predicted_sgv: float,
    lower_bound: float | None = None,
    upper_bound: float | None = None,
) -> PredictionPoint:
    point = PredictionPoint()
    point.run_id = run_id
    point.timestamp = timestamp
    point.predicted_sgv = predicted_sgv
    point.lower_bound = lower_bound
    point.upper_bound = upper_bound
    return point


class TestPredictionRun:
    """Creation, field defaults, and relationship integrity."""

    def test_create_minimal_run(self, db_session, patient_user):
        run = _make_run(
            user_id=patient_user.id,
            context_end_at=datetime.now(UTC),
            horizon_minutes=60,
            model_version="v1.0.0",
        )
        db_session.add(run)
        db_session.commit()

        assert run.id is not None
        assert run.user_id == patient_user.id
        assert run.generated_at is not None  # server_default
        assert run.horizon_minutes == 60
        assert run.model_version == "v1.0.0"
        assert run.feature_version is None

    def test_create_run_with_feature_version(self, db_session, patient_user):
        run = _make_run(
            user_id=patient_user.id,
            context_end_at=datetime.now(UTC),
            horizon_minutes=120,
            model_version="v1.0.0",
            feature_version="f2",
        )
        db_session.add(run)
        db_session.commit()
        assert run.feature_version == "f2"

    def test_generated_at_has_server_default(self, db_session, patient_user):
        run = _make_run(
            user_id=patient_user.id,
            context_end_at=datetime.now(UTC),
            horizon_minutes=60,
            model_version="v1.0.0",
        )
        db_session.add(run)
        db_session.commit()
        assert run.generated_at is not None
        delta = datetime.now(UTC) - run.generated_at
        assert abs(delta.total_seconds()) < 30  # within 30s of now


class TestPredictionPoint:
    """Individual forecast point creation and ordering."""

    def test_create_point_with_bounds(self, db_session, patient_user):
        run = _make_run(
            user_id=patient_user.id,
            context_end_at=datetime.now(UTC),
            horizon_minutes=60,
            model_version="v1.0.0",
        )
        db_session.add(run)
        db_session.flush()

        point = _make_point(
            run_id=run.id,
            timestamp=datetime.now(UTC) + timedelta(minutes=5),
            predicted_sgv=120.0,
            lower_bound=100.0,
            upper_bound=140.0,
        )
        db_session.add(point)
        db_session.commit()

        assert point.id is not None
        assert point.run_id == run.id
        assert point.predicted_sgv == 120.0
        assert point.lower_bound == 100.0
        assert point.upper_bound == 140.0

    def test_create_point_without_bounds(self, db_session, patient_user):
        run = _make_run(
            user_id=patient_user.id,
            context_end_at=datetime.now(UTC),
            horizon_minutes=60,
            model_version="v1.0.0",
        )
        db_session.add(run)
        db_session.flush()

        point = _make_point(
            run_id=run.id,
            timestamp=datetime.now(UTC) + timedelta(minutes=10),
            predicted_sgv=85.0,
        )
        db_session.add(point)
        db_session.commit()

        assert point.lower_bound is None
        assert point.upper_bound is None

    def test_points_ordered_by_timestamp(self, db_session, patient_user):
        run = _make_run(
            user_id=patient_user.id,
            context_end_at=datetime.now(UTC),
            horizon_minutes=60,
            model_version="v1.0.0",
        )
        db_session.add(run)
        db_session.flush()

        base = datetime.now(UTC)
        for i in [30, 5, 20, 10, 0]:
            db_session.add(
                _make_point(
                    run_id=run.id,
                    timestamp=base + timedelta(minutes=i),
                    predicted_sgv=float(100 + i),
                )
            )
        db_session.commit()

        # Refresh to get relationship with order_by applied.
        db_session.refresh(run)
        timestamps = [p.timestamp for p in run.points]
        assert timestamps == sorted(timestamps), (
            "points must be ordered by timestamp via relationship"
        )


class TestPredictionDuplicatePolicy:
    """Explicit policy: unique(run_id, timestamp) prevents duplicate points."""

    def test_duplicate_point_rejected(self, db_session, patient_user):
        run = _make_run(
            user_id=patient_user.id,
            context_end_at=datetime.now(UTC),
            horizon_minutes=60,
            model_version="v1.0.0",
        )
        db_session.add(run)
        db_session.flush()

        ts = datetime.now(UTC) + timedelta(minutes=5)
        p1 = _make_point(run_id=run.id, timestamp=ts, predicted_sgv=120.0)
        db_session.add(p1)
        db_session.commit()

        p2 = _make_point(run_id=run.id, timestamp=ts, predicted_sgv=125.0)
        with pytest.raises(IntegrityError):
            db_session.add(p2)
            db_session.commit()

    def test_same_timestamp_different_run_allowed(self, db_session, patient_user):
        ts = datetime.now(UTC) + timedelta(minutes=5)

        r1 = _make_run(
            user_id=patient_user.id,
            context_end_at=datetime.now(UTC),
            horizon_minutes=60,
            model_version="v1.0.0",
        )
        r2 = _make_run(
            user_id=patient_user.id,
            context_end_at=datetime.now(UTC),
            horizon_minutes=120,
            model_version="v1.0.0",
        )
        db_session.add_all([r1, r2])
        db_session.flush()

        p1 = _make_point(run_id=r1.id, timestamp=ts, predicted_sgv=120.0)
        p2 = _make_point(run_id=r2.id, timestamp=ts, predicted_sgv=130.0)
        db_session.add_all([p1, p2])
        db_session.commit()

        assert p1.id != p2.id


class TestPredictionCascade:
    """Deleting a run cascades to its points."""

    def test_delete_run_removes_points(self, db_session, patient_user):
        run = _make_run(
            user_id=patient_user.id,
            context_end_at=datetime.now(UTC),
            horizon_minutes=60,
            model_version="v1.0.0",
        )
        db_session.add(run)
        db_session.flush()

        for i in range(12):
            db_session.add(
                _make_point(
                    run_id=run.id,
                    timestamp=datetime.now(UTC) + timedelta(minutes=5 * i),
                    predicted_sgv=float(100 + i),
                )
            )
        db_session.commit()

        run_id = run.id
        db_session.delete(run)
        db_session.commit()

        remaining = db_session.query(PredictionPoint).filter_by(run_id=run_id).count()
        assert remaining == 0


class TestPredictionRunQuery:
    """Query patterns the plan expects to work."""

    def test_insert_and_query_back_ordered(self, db_session, patient_user):
        run = _make_run(
            user_id=patient_user.id,
            context_end_at=datetime.now(UTC),
            horizon_minutes=60,
            model_version="v1.0.0",
        )
        db_session.add(run)
        db_session.flush()

        base = datetime.now(UTC)
        for i in range(12):
            db_session.add(
                _make_point(
                    run_id=run.id,
                    timestamp=base + timedelta(minutes=5 * i),
                    predicted_sgv=float(100 + i * 3),
                )
            )
        db_session.commit()

        # Query points ordered by timestamp.
        points = (
            db_session.query(PredictionPoint)
            .filter_by(run_id=run.id)
            .order_by(PredictionPoint.timestamp)
            .all()
        )
        assert len(points) == 12
        for i in range(1, len(points)):
            assert points[i].timestamp > points[i - 1].timestamp

    def test_query_multiple_runs_distinct(self, db_session, patient_user):
        base = datetime.now(UTC)
        r1 = _make_run(
            user_id=patient_user.id,
            context_end_at=base - timedelta(hours=2),
            horizon_minutes=60,
            model_version="v1.0.0",
        )
        r2 = _make_run(
            user_id=patient_user.id,
            context_end_at=base - timedelta(hours=1),
            horizon_minutes=60,
            model_version="v1.0.0",
        )
        db_session.add_all([r1, r2])
        db_session.flush()

        db_session.add(_make_point(run_id=r1.id, timestamp=base, predicted_sgv=100.0))
        db_session.add(_make_point(run_id=r2.id, timestamp=base, predicted_sgv=110.0))
        db_session.commit()

        p1 = db_session.query(PredictionPoint).filter_by(run_id=r1.id).first()
        p2 = db_session.query(PredictionPoint).filter_by(run_id=r2.id).first()
        assert p1.predicted_sgv == 100.0
        assert p2.predicted_sgv == 110.0
