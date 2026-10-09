"""Free-host process driver for the existing DB worker.

Idle waiting touches only a local marker. It does not poll Neon or create model
requests. Service startup checks retained queue/expired leases; accepted writes
wake the same run_one implementation used by the original worker.
"""
import os
import time
from pathlib import Path

from . import worker
from .db import connection
from .cloud_transport import validate_cloud_mode


def marker_version(path):
    try:
        return path.stat().st_mtime_ns
    except FileNotFoundError:
        return 0


def queued_work_exists():
    with connection() as conn,conn.cursor() as cur:
        cur.execute("SELECT EXISTS(SELECT 1 FROM review_jobs WHERE status='QUEUED') AS pending")
        return cur.fetchone()['pending']


class Driver:
    def __init__(self,marker):
        self.marker = marker
        self.seen = -1
        self.boot_recovery_at = time.monotonic()+35
        self.next_pending_check = None

    def step(self):
        now = time.monotonic()
        changed = marker_version(self.marker)
        recovery_due = self.boot_recovery_at is not None and now >= self.boot_recovery_at
        pending_due = self.next_pending_check is not None and now >= self.next_pending_check
        if changed == self.seen and not recovery_due and not pending_due:
            return False  # idle: no DB calls and no inference calls
        worker.recover_orphaned_jobs()
        while worker.run_one():
            pass
        # Retain the original 2-second queue backoff after DEMO lease recovery.
        # Only QUEUED work is revisited; UNKNOWN_OUTCOME is never dispatched.
        self.next_pending_check = now+3 if queued_work_exists() else None
        self.seen = changed
        if recovery_due:
            self.boot_recovery_at = None
        return True


def initialize_remote_state():
    if worker.APP_MODE == 'DEMO':
        worker.set_remote_state("LOCAL_ONLY","explicit DEMO mode; cloud CPU worker")
    else:
        worker.refresh_remote_state()


def main():
    validate_cloud_mode()
    marker = Path(os.environ["DORILAB_WORKER_WAKE_FILE"])
    marker.parent.mkdir(parents=True,exist_ok=True)
    driver = Driver(marker)
    while True:
        try:
            if driver.seen == -1:
                initialize_remote_state()
            driver.step()
        except Exception as error:
            print(f"CLOUD_WORKER_WAITING: {type(error).__name__}",flush=True)
            time.sleep(5)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
