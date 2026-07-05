"""pytest configuration — disable scheduler during import to prevent hangs."""

import os

os.environ["BGMON_DISABLE_SCHEDULER"] = "true"
