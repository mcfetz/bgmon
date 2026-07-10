"""Leader election service tests."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from bgmon_api.models import SchedulerLeader
from bgmon_api.services.leader import RowLeaseLeader


def _leader_row(db_session):
    return db_session.get(SchedulerLeader, 1)


def test_initial_acquire_succeeds(app, db_session):
    with app.app_context():
        leader = RowLeaseLeader()

        result = leader.try_acquire()
        row = _leader_row(db_session)

        assert result is True
        assert leader.is_leader is True
        assert row is not None
        assert row.instance_id == leader.instance_id


def test_second_instance_cannot_acquire(app, db_session):
    with app.app_context():
        first = RowLeaseLeader()
        second = RowLeaseLeader()

        assert first.try_acquire() is True
        assert second.try_acquire() is False
        assert second.is_leader is False
        assert _leader_row(db_session).instance_id == first.instance_id


def test_takeover_expired_lease(app, db_session):
    with app.app_context():
        first = RowLeaseLeader()
        second = RowLeaseLeader()

        assert first.try_acquire() is True
        row = _leader_row(db_session)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db_session.commit()

        assert second.try_acquire() is True
        assert second.is_leader is True
        assert _leader_row(db_session).instance_id == second.instance_id


def test_renew_maintains_leadership(app, db_session):
    with app.app_context():
        leader = RowLeaseLeader()

        assert leader.try_acquire() is True
        previous_expiry = _leader_row(db_session).expires_at

        assert leader.renew() is True
        assert leader.is_leader is True
        assert _leader_row(db_session).expires_at > previous_expiry


def test_renew_fails_when_not_leader(app):
    with app.app_context():
        leader = RowLeaseLeader()

        assert leader.renew() is False
        assert leader.is_leader is False


def test_resign_releases_leadership(app, db_session):
    with app.app_context():
        leader = RowLeaseLeader()

        assert leader.try_acquire() is True
        leader.resign()
        row = _leader_row(db_session)

        assert leader.is_leader is False
        assert row is not None
        assert row.expires_at < datetime.now(UTC)


def test_daemon_renew_loop_leader(app):
    with app.app_context():
        leader = RowLeaseLeader()
        leader.try_acquire()

        with patch.object(leader, "renew", return_value=True) as mock_renew:
            leader.daemon_renew_loop()

        mock_renew.assert_called_once_with()


def test_daemon_renew_loop_acquires(app):
    with app.app_context():
        leader = RowLeaseLeader()

        with patch.object(leader, "try_acquire", return_value=True) as mock_try_acquire:
            leader.daemon_renew_loop()

        mock_try_acquire.assert_called_once_with()


def test_instance_id_consistent():
    leader = RowLeaseLeader()

    first = leader.instance_id
    second = leader.instance_id

    assert first == second
    assert isinstance(first, str)
    assert len(first) == 32
