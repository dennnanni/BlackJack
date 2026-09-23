"""Background cleanup. Every central replica runs it: the trimmer lock keeps two
replicas from trimming at the same time."""
import logging
import threading
import time
from central_server import db
from central_server.config import (BUYIN_GRACE, DB_PROBE_INTERVAL, DEAD_SERVERS_RETENTION,
                                   SEAT_TAKEOVER, TRIMMER_INTERVAL)

APPLIED_ROUND_RETENTION = 7 * 24 * 3600 # a week
# dead servers and old rounds are removed once every PRUNE_EVERY trims
PRUNE_EVERY = 5

logger = logging.getLogger(__name__)


def _trim(prune):
    with db.trimmer_lock() as locked:
        if not locked:
            logger.info('another replica is trimming, skipping')
            return
        closed = db.close_abandoned_buy_ins(BUYIN_GRACE)
        if closed:
            logger.info(f'closed {len(closed)} buy ins')
        if prune:
            deleted = db.remove_dead_servers(DEAD_SERVERS_RETENTION)
            db.prune_old_rounds(APPLIED_ROUND_RETENTION)
            if deleted:
                logger.info(f'deleted {deleted} game servers')


def _run():
    db_up_since = None
    last_trim = time.monotonic()
    trims = 0
    while True:
        time.sleep(DB_PROBE_INTERVAL)
        now = time.monotonic()
        if not db.ping():
            db_up_since = None
            continue
        if db_up_since is None:
            db_up_since = now
        # checks how long after a missed reply from the db before trimming to allow consistency
        if now - db_up_since < SEAT_TAKEOVER or now - last_trim < TRIMMER_INTERVAL:
            continue
        last_trim = now
        trims += 1
        try:
            _trim(prune=trims % PRUNE_EVERY == 0)
        except Exception:
            logger.exception('trimming failed')


def start_trimmer():
    threading.Thread(target=_run, name='trimmer', daemon=True).start()
