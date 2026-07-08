"""Thread tracing — logs thread count and names before/after scheduler jobs."""

import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

TRACE_LOG = "/tmp/bgmon-threads.log"
_last_count = 0


def _read_threads() -> list[str]:
    """Return full thread names for this process (not truncated like ps)."""
    return [th.name for th in threading.enumerate()]


def _read_status_threads() -> int:
    """Read /proc/self/status Threads field."""
    try:
        with open(f"/proc/{os.getpid()}/status") as f:
            for line in f:
                if line.startswith("Threads:"):
                    return int(line.split()[1])
    except Exception:
        pass
    return 0


def snapshot(job_name: str, phase: str) -> None:
    """Log thread count+names at a trace point.

    Args:
        job_name: scheduler job id (libre_fetch, alarm_eval, ...)
        phase: "before", "after", or "periodic"
    """
    global _last_count
    count = _read_status_threads()
    threads = _read_threads()
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    # Group thread names by prefix
    from collections import Counter
    groups = Counter(
        t[:30] if "ThreadPoolExecutor" in t else t for t in threads
    ).most_common()
    group_str = "; ".join(f"{n}x {name}" for name, n in groups)

    delta = count - _last_count if _last_count else 0
    _last_count = count

    try:
        with open(TRACE_LOG, "a") as f:
            f.write(
                f"[{now}] {job_name:20s} {phase:8s} "
                f"threads={count:4d} (Δ={delta:+d}) "
                f"groups=[{group_str}]\n"
            )
    except Exception:
        pass


def start_periodic_snapshot(interval_s: int = 300) -> None:
    """Start a background thread that takes periodic thread snapshots."""

    def _loop() -> None:
        while True:
            time.sleep(interval_s)
            try:
                snapshot("(periodic)", "snapshot")
            except Exception:
                pass

    t = threading.Thread(target=_loop, daemon=True, name="thread-tracer")
    t.start()
