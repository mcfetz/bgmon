"""Bootstrap admin user and seed default data on first startup."""

import logging

from bgmon_api.config import Config
from bgmon_api.extensions import db
from bgmon_api.models import SnoozePreset, Threshold, User, UserRole
from bgmon_api.utils import transactional_session

logger = logging.getLogger(__name__)


def bootstrap_admin() -> None:
    """Create admin user from env vars if no users exist."""
    if not Config.BOOTSTRAP_ADMIN_EMAIL or not Config.BOOTSTRAP_ADMIN_PASSWORD:
        return
    try:
        if User.query.first() is not None:
            return
    except Exception:
        # Tables not yet created (first deploy before migration)
        return

    admin = User(
        email=Config.BOOTSTRAP_ADMIN_EMAIL,
        display_name="Admin",
        role=UserRole.ADMIN,
    )
    admin.set_password(Config.BOOTSTRAP_ADMIN_PASSWORD)
    db.session.add(admin)
    db.session.flush()

    patient = User(
        email="fiona@familie-heise.de",
        display_name="Fiona",
        role=UserRole.PATIENT,
    )
    patient.set_password(Config.BOOTSTRAP_ADMIN_PASSWORD)
    db.session.add(patient)
    db.session.flush()

    for user in [admin, patient]:
        defaults = Threshold(user_id=user.id)
        db.session.add(defaults)
        for label, mins in [
            ("5 min", 5),
            ("10 min", 10),
            ("15 min", 15),
            ("20 min", 20),
            ("30 min", 30),
            ("60 min", 60),
        ]:
            db.session.add(SnoozePreset(user_id=user.id, label=label, duration_minutes=mins))

    with transactional_session():
        pass  # commit handled by context manager
    logger.info("Bootstrapped admin and patient users")
