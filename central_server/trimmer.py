import logging
import threading
import time
from central_server import db
from central_server.config import BUYIN_GRACE, DEAD_SERVERS_RETENTION, TRIMMER_INTERVAL

APPLIED_ROUND_RETENTION = 7 * 24 * 3600 # a week

logger = logging.getLogger(__name__)

def _run():
    i = 0
    deleted, closed = None, []
    while True:
        time.sleep(TRIMMER_INTERVAL)
        i += 1
        if i == 5:
            deleted = db.remove_dead_servers(DEAD_SERVERS_RETENTION)
            db.prune_old_rounds(APPLIED_ROUND_RETENTION)
            i = 0
        closed = db.close_abandoned_buy_ins(BUYIN_GRACE)
        if closed:
            logger.info(f'closed {len(closed)} buy ins')
        if deleted: 
            logger.info(f'deleted {deleted} game servers')
            deleted = None


def start_trimmer():
    threading.Thread(target=_run, name='trimmer', daemon=True).start()
