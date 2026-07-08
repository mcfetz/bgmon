"""Standalone scheduler process — runs outside Gunicorn."""
import logging
import os
import sys

os.environ['BGMON_STANDALONE_SCHEDULER'] = '1'

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Prevent this process from starting multiple times
PID_FILE = "/tmp/bgmon-scheduler.pid"

def _check_pid() -> bool:
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        logger.error("Scheduler already running (pid=%d)", pid)
        return False
    except (FileNotFoundError, OSError):
        pass
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    return True


def main():
    if not _check_pid():
        sys.exit(1)

    from bgmon_api.app import (
        create_app,
        leader,
        scheduler,
    )

    app = create_app()

    # Start thread tracing (logs thread count to /tmp/bgmon-threads.log)
    from bgmon_api.thread_tracer import start_periodic_snapshot
    start_periodic_snapshot(interval_s=300)

    with app.app_context():
        leader.try_acquire()
        # scheduler is already started by create_app() (called during import)
        logger.info("Standalone scheduler started (leader=%s)", leader.is_leader)

    import signal

    def shutdown(signum, frame):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)
        if os.path.exists(PID_FILE):
            os.unlink(PID_FILE)
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Keep alive
    import time
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
