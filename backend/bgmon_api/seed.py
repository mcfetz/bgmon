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
    if User.query.first() is not None:
        return

    with transactional_session():
        admin = User()
        admin.email = Config.BOOTSTRAP_ADMIN_EMAIL
        admin.display_name = "Admin"
        admin.role = UserRole.ADMIN
        admin.set_password(Config.BOOTSTRAP_ADMIN_PASSWORD)
        db.session.add(admin)
        db.session.flush()

        patient = User()
        patient.email = "fiona@familie-heise.de"
        patient.display_name = "Fiona"
        patient.role = UserRole.PATIENT
        patient.set_password(Config.BOOTSTRAP_ADMIN_PASSWORD)
        db.session.add(patient)
        db.session.flush()

        for user in [admin, patient]:
            defaults = Threshold()
            defaults.user_id = user.id
            db.session.add(defaults)
            for label, mins in [
                ("5 min", 5),
                ("10 min", 10),
                ("15 min", 15),
                ("20 min", 20),
                ("30 min", 30),
                ("60 min", 60),
            ]:
                preset = SnoozePreset()
                preset.user_id = user.id
                preset.label = label
                preset.duration_minutes = mins
                db.session.add(preset)

    logger.info("Bootstrapped admin and patient users")
