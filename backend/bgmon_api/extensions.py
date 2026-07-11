"""Shared Flask extensions to avoid circular imports."""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

__all__ = ["db", "migrate", "limiter"]

db: SQLAlchemy = SQLAlchemy()
migrate: Migrate = Migrate()
limiter: Limiter = Limiter(
    get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)
