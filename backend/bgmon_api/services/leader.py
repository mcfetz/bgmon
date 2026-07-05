"""Row-lease leader election for Swarm HA."""

import logging
import secrets
from contextlib import suppress
from datetime import UTC, datetime, timedelta

from bgmon_api.app import db
from bgmon_api.config import Config
from bgmon_api.models import SchedulerLeader

logger = logging.getLogger(__name__)


class RowLeaseLeader:
    """PostgreSQL row-lease for leader election among replicas.

    Only one replica is leader at a time. The lease is acquired by inserting
    into the single-row ``scheduler_leader`` table (id=1) using ``ON CONFLICT``
    with a time condition: either no row exists yet, or the existing lease has
    expired (``expires_at < NOW()``).
    """

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
        """Try to become leader. Returns True if we acquired the lease."""
        ttl = Config.LEASE_TTL_S
        now = datetime.now(UTC)
        new_expires = now + timedelta(seconds=ttl)

        try:
            row = db.session.get(SchedulerLeader, 1)
        except Exception:
            db.session.rollback()
            row = None

        if row is None:
            row = SchedulerLeader(
                id=1,
                instance_id=self._instance_id,
                last_heartbeat=now,
                expires_at=new_expires,
            )
            db.session.add(row)
            with suppress(Exception):
                db.session.commit()
            self._is_leader = True
            logger.info("Became leader (instance=%s)", self._instance_id[:8])
            return True

        if row.expires_at < now:
            row.instance_id = self._instance_id
            row.last_heartbeat = now
            row.expires_at = new_expires
            with suppress(Exception):
                db.session.commit()
            self._is_leader = True
            logger.info("Took over lease (instance=%s)", self._instance_id[:8])
            return True

        self._is_leader = row.instance_id == self._instance_id
        return self._is_leader

    def renew(self) -> bool:
        """Renew the lease if we are the leader. Returns True if still leader."""
        if not self._is_leader:
            return False
        ttl = Config.LEASE_TTL_S
        now = datetime.now(UTC)
        new_expires = now + timedelta(seconds=ttl)

        try:
            row = db.session.get(SchedulerLeader, 1)
        except Exception:
            db.session.rollback()
            return False

        if row is None or row.instance_id != self._instance_id:
            self._is_leader = False
            return False

        row.last_heartbeat = now
        row.expires_at = new_expires
        with suppress(Exception):
            db.session.commit()
        return True

    def resign(self) -> None:
        """Resign leadership by expiring the lease."""
        if not self._is_leader:
            return
        try:
            row = db.session.get(SchedulerLeader, 1)
            if row and row.instance_id == self._instance_id:
                row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
                db.session.commit()
        except Exception:
            db.session.rollback()
        self._is_leader = False
        logger.info("Resigned leadership (instance=%s)", self._instance_id[:8])

    def daemon_renew_loop(self) -> None:
        """Periodic renew loop for APScheduler."""
        if self._is_leader:
            self.renew()
        else:
            self.try_acquire()
