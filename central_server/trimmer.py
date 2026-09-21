import threading
import time
from central_server import db
from central_server.config import BUYIN_GRACE, TRIMMER_INTERVAL

APPLIED_ROUND_RETENTION = 7 * 24 * 3600 # a week


def _run():
    i = 0
    while True:
        time.sleep(TRIMMER_INTERVAL)
        i += 1
        if i == 5:
            db.prune_old_rounds(APPLIED_ROUND_RETENTION)
            i = 0
        closed = db.close_abandoned_buy_ins(BUYIN_GRACE)
        if closed:
            print(f'[trimmer] closed {len(closed)} buy ins')


def start_trimmer():
    threading.Thread(target=_run, name='trimmer', daemon=True).start()
