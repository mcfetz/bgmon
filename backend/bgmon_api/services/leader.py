"""Row-lease leader election for Swarm HA."""

import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from bgmon_api.config import Config
from bgmon_api.extensions import db
from bgmon_api.models import SchedulerLeader

logger = logging.getLogger(__name__)


class RowLeaseLeader:
    """PostgreSQL row-lease for leader election among replicas."""

    def __init__(self) -> None:
        self._instance_id = secrets.token_hex(16)
        self._is_leader = False

    @property
    def instance_id(self) -> str:
        return self._instance_id

    @property
    def is_leader(self) -> bool:
        return self._is_leader

    def try_acquire(self) -> bool:
        """Try to become leader. Returns True if we acquired or still hold the lease."""
        ttl = Config.LEASE_TTL_S
        now = datetime.now(UTC)
        new_expires = now + timedelta(seconds=ttl)
        leader_table = SchedulerLeader.__table__

        stmt = (
            insert(leader_table)
            .values(
                id=1,
                instance_id=self._instance_id,
                last_heartbeat=now,
                expires_at=new_expires,
            )
            .on_conflict_do_update(
                index_elements=[leader_table.c.id],
                set_={
                    "instance_id": self._instance_id,
                    "last_heartbeat": now,
                    "expires_at": new_expires,
                },
                where=(
                    (leader_table.c.expires_at < now)
                    | (leader_table.c.instance_id == self._instance_id)
                ),
            )
            .returning(leader_table.c.instance_id)
        )

        try:
            owner_id = db.session.execute(stmt).scalar_one_or_none()
            db.session.commit()
        except SQLAlchemyError as exc:
            logger.error("Failed to acquire leader lease: %s", exc)
            db.session.rollback()
            self._is_leader = False
            return False

        self._is_leader = owner_id == self._instance_id
        if self._is_leader:
            logger.info("Leader lease acquired/confirmed (instance=%s)", self._instance_id[:8])

        return self._is_leader

    def renew(self) -> bool:
        """Renew the lease if we are still the leader. Returns True if still leader."""
        if not self._is_leader:
            return False

        ttl = Config.LEASE_TTL_S
        now = datetime.now(UTC)
        new_expires = now + timedelta(seconds=ttl)
        leader_table = SchedulerLeader.__table__

        stmt = (
            update(leader_table)
            .where(
                leader_table.c.id == 1,
                leader_table.c.instance_id == self._instance_id,
                leader_table.c.expires_at >= now,
            )
            .values(
                last_heartbeat=now,
                expires_at=new_expires,
            )
            .returning(leader_table.c.instance_id)
        )

        try:
            owner_id = db.session.execute(stmt).scalar_one_or_none()
            db.session.commit()
        except SQLAlchemyError as exc:
            logger.error("Failed to renew leader lease: %s", exc)
            db.session.rollback()
            self._is_leader = False
            return False

        self._is_leader = owner_id == self._instance_id
        return self._is_leader

    def resign(self) -> None:
        """Resign leadership by expiring the lease."""
        if not self._is_leader:
            return
        try:
            row = db.session.get(SchedulerLeader, 1)
            if row and row.instance_id == self._instance_id:
                row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
                db.session.commit()
                logger.info("Resigned leadership (instance=%s)", self._instance_id[:8])
        except SQLAlchemyError as exc:
            logger.error("Failed to resign leadership: %s", exc)
            db.session.rollback()
        finally:
            self._is_leader = False

    def daemon_renew_loop(self) -> None:
        """Periodic renew loop for APScheduler."""
        if self._is_leader:
            self.renew()
        else:
            self.try_acquire()
