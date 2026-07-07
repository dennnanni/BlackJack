"""Failure detection: a background thread that watches game-server
heartbeats and reports servers going offline/online.

Exclusion from dispatch does not depend on this thread (the dispatcher
filters on last_seen itself); the reaper makes failure detection observable
and hosts periodic cleanup.
"""
import threading
import time

from central_server import db
from central_server.config import HEARTBEAT_TTL, REAPER_INTERVAL

# After a week no result retry can plausibly still be in flight.
APPLIED_ROUND_RETENTION = 7 * 24 * 3600


def _scan(known_stale):
    now = time.time()
    stale = {s.id for s in db.get_servers() if s.last_seen < now - HEARTBEAT_TTL}
    for server_id in stale - known_stale:
        print(f'[reaper] game server {server_id} missed its heartbeats: '
              f'considered offline, removed from dispatch')
    for server_id in known_stale - stale:
        print(f'[reaper] game server {server_id} is back online')
    return stale


def _run():
    known_stale = set()
    while True:
        time.sleep(REAPER_INTERVAL)
        known_stale = _scan(known_stale)
        db.prune_applied_rounds(APPLIED_ROUND_RETENTION)


def start_reaper():
    threading.Thread(target=_run, name='reaper', daemon=True).start()
