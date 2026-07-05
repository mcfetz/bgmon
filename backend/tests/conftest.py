"""pytest configuration — set test env vars before any app imports."""

import os

# MUST run before any bgmon_api import: app.py calls create_app() at module load.
os.environ["BGMON_DISABLE_SCHEDULER"] = "true"
os.environ["BGMON_SECRET_KEY"] = os.environ.get("BGMON_SECRET_KEY", "test-secret-key")
os.environ.setdefault(
    "BGMON_DATABASE_URL",
    "postgresql://bgmon:bgmon@localhost:5432/bgmon_test",
)
