"""Tests for transactional integrity and leader election."""

from datetime import UTC, datetime, timedelta

import pytest


class TestTransactionalSession:
    """Test the transactional_session context manager."""

    def test_transactional_session_commits_on_success(self, db_session, app):
        """Test that transactional_session commits when no exception occurs."""
        from bgmon_api.models import User, UserRole
        from bgmon_api.utils import transactional_session

        with app.app_context():
            with transactional_session():
                user = User(
                    email="tx_test@example.com",
                    display_name="TX Test",
                    role=UserRole.PATIENT,
                )
                user.set_password("password")
                db_session.add(user)

            # Verify committed
            persisted = User.query.filter_by(email="tx_test@example.com").first()
            assert persisted is not None

    def test_transactional_session_rollback_on_exception(self, db_session, app):
        """Test that transactional_session rolls back on exception."""
        from bgmon_api.models import User, UserRole
        from bgmon_api.utils import transactional_session

        with app.app_context():
            try:
                with transactional_session():
                    user = User(
                        email="rollback_test@example.com",
                        display_name="Rollback Test",
                        role=UserRole.PATIENT,
                    )
                    user.set_password("password")
                    db_session.add(user)
                    raise ValueError("Intentional error")
            except ValueError:
                pass

            # Verify not persisted (rolled back)
            persisted = User.query.filter_by(email="rollback_test@example.com").first()
            assert persisted is None


class TestLeaderElection:
    """Test row-lease leader election logic."""

    def test_first_instance_becomes_leader(self, db_session, app):
        """Test that first instance to try_acquire becomes leader."""
        from bgmon_api.services.leader import RowLeaseLeader

        with app.app_context():
            leader = RowLeaseLeader()
            result = leader.try_acquire()
            assert result is True
            assert leader.is_leader is True

    def test_second_instance_does_not_become_leader(self, db_session, app):
        """Test that second instance cannot become leader while first holds it."""
        from bgmon_api.services.leader import RowLeaseLeader

        with app.app_context():
            leader1 = RowLeaseLeader()
            leader2 = RowLeaseLeader()

            assert leader1.try_acquire() is True
            assert leader1.is_leader is True

            # Second instance tries to acquire
            assert leader2.try_acquire() is False
            assert leader2.is_leader is False

    def test_leader_renews_lease(self, db_session, app):
        """Test that leader can renew its lease."""
        from bgmon_api.services.leader import RowLeaseLeader

        with app.app_context():
            leader = RowLeaseLeader()
            leader.try_acquire()
            assert leader.is_leader is True

            # Renew
            result = leader.renew()
            assert result is True
            assert leader.is_leader is True

    def test_non_leader_cannot_renew(self, db_session, app):
        """Test that non-leader cannot renew."""
        from bgmon_api.services.leader import RowLeaseLeader

        with app.app_context():
            leader1 = RowLeaseLeader()
            leader2 = RowLeaseLeader()

            leader1.try_acquire()
            leader2.try_acquire()

            # leader2 tries to renew (not leader)
            assert leader2.renew() is False

    def test_leader_resignation(self, db_session, app):
        """Test that leader can resign."""
        from bgmon_api.services.leader import RowLeaseLeader

        with app.app_context():
            leader1 = RowLeaseLeader()
            leader2 = RowLeaseLeader()

            leader1.try_acquire()
            assert leader1.is_leader is True

            # Resign
            leader1.resign()
            assert leader1.is_leader is False

            # Now leader2 can acquire
            assert leader2.try_acquire() is True
            assert leader2.is_leader is True


class TestAuthSessionTransactions:
    """Test that auth operations use transactions correctly."""

    def test_login_creates_session_transactionally(self, client, patient_user):
        """Test that login creates session atomically."""
        from bgmon_api.models import Session

        response = client.post(
            "/api/auth/login",
            json={"email": "patient@example.com", "password": "test_password"},
        )
        assert response.status_code == 200
        token = response.get_json()["token"]

        # Verify session exists in DB
        session = Session.query.filter_by(token=token).first()
        assert session is not None
        assert session.user_id == patient_user.id

    def test_logout_deletes_session_transactionally(self, client, patient_session):
        """Test that logout deletes session atomically."""
        from bgmon_api.models import Session

        # Logout
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {patient_session.token}"},
        )
        assert response.status_code == 200

        # Verify session is deleted
        session = Session.query.filter_by(token=patient_session.token).first()
        assert session is None


class TestDatabaseIntegrity:
    """Test database constraints and integrity."""

    def test_user_email_uniqueness_enforced(self, db_session, app, patient_user):
        """Test that user email must be unique."""
        from sqlalchemy.exc import IntegrityError

        from bgmon_api.models import User, UserRole

        with app.app_context():
            # Try to create user with same email
            duplicate = User(
                email="patient@example.com",
                display_name="Duplicate",
                role=UserRole.PATIENT,
            )
            db_session.add(duplicate)

            with pytest.raises(IntegrityError):
                db_session.commit()

    def test_session_token_uniqueness(self, db_session, app, patient_user):
        """Test that session tokens are unique."""
        from sqlalchemy.exc import IntegrityError

        from bgmon_api.models import Session

        with app.app_context():
            session1 = Session(
                user_id=patient_user.id,
                token="same-token-123",
                expires_at=datetime.now(UTC) + timedelta(days=30),
            )
            session2 = Session(
                user_id=patient_user.id,
                token="same-token-123",  # Duplicate token
                expires_at=datetime.now(UTC) + timedelta(days=30),
            )
            db_session.add(session1)
            db_session.flush()
            db_session.add(session2)

            with pytest.raises(IntegrityError):
                db_session.commit()

    def test_user_cascade_delete(self, db_session, app):
        """Test that deleting user cascades to related records."""
        from bgmon_api.models import Session, Threshold, User, UserRole

        with app.app_context():
            user = User(
                email="cascade_test@example.com",
                display_name="Cascade Test",
                role=UserRole.PATIENT,
            )
            user.set_password("password")
            db_session.add(user)
            db_session.flush()

            # Add related records
            threshold = Threshold(user_id=user.id)
            session = Session(
                user_id=user.id,
                expires_at=datetime.now(UTC) + timedelta(days=30),
            )
            db_session.add(threshold)
            db_session.add(session)
            db_session.commit()

            user_id = user.id

            # Delete user
            db_session.delete(user)
            db_session.commit()

            # Verify related records are deleted
            assert User.query.get(user_id) is None
            assert Threshold.query.filter_by(user_id=user_id).first() is None
            assert Session.query.filter_by(user_id=user_id).first() is None
