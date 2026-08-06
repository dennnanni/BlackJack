"""Periodic cleanup thread.

Failure detection itself needs no thread: `web.play` filters servers on
`last_seen` at dispatch time, so a server that stops heartbeating drops out on
its own. All that is left to do on a timer is trimming the idempotency ledger.
"""
import threading
import time

from central_server import db
from central_server.config import REAPER_INTERVAL

# After a week no result retry can plausibly still be in flight.
APPLIED_ROUND_RETENTION = 7 * 24 * 3600


def _run():
    while True:
        time.sleep(REAPER_INTERVAL)
        db.prune_applied_rounds(APPLIED_ROUND_RETENTION)


def start_reaper():
    threading.Thread(target=_run, name='reaper', daemon=True).start()
