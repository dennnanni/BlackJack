import json
import sqlite3
import time
from contextlib import contextmanager

from shared.messages import Result


class Outbox:
    def __init__(self, path):
        self.path = path
        with self._connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS pending ('
                         'round_id TEXT PRIMARY KEY,'
                         'payload TEXT NOT NULL,'
                         'created_at REAL NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS pending_leave ('
                         'buy_in_id TEXT PRIMARY KEY,'
                         'created_at REAL NOT NULL)')

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.path)
        try:
            with conn:  # one transaction, committed on success
                yield conn
        finally:
            conn.close()

    def enqueue(self, round_id, results):
        payload = json.dumps([r.to_dict() for r in results])
        with self._connection() as conn:
            conn.execute('INSERT OR IGNORE INTO pending VALUES (?, ?, ?)',
                         (round_id, payload, time.time()))

    def pending(self):
        """Undelivered rounds, oldest first."""
        with self._connection() as conn:
            rows = conn.execute(
                'SELECT round_id, payload FROM pending ORDER BY created_at').fetchall()
        return [(round_id, [Result.from_dict(r) for r in json.loads(payload)])
                for round_id, payload in rows]

    def ack(self, round_id):
        """Delivery confirmed by central: the entry is no longer needed."""
        with self._connection() as conn:
            conn.execute('DELETE FROM pending WHERE round_id = ?', (round_id,))

    def enqueue_leave(self, buy_in_id):
        """A player left the table: central must close their buy-in."""
        with self._connection() as conn:
            conn.execute('INSERT OR IGNORE INTO pending_leave VALUES (?, ?)',
                         (buy_in_id, time.time()))

    def pending_leaves(self):
        """Buy-ins still to close, oldest first."""
        with self._connection() as conn:
            rows = conn.execute(
                'SELECT buy_in_id FROM pending_leave ORDER BY created_at').fetchall()
        return [buy_in_id for (buy_in_id,) in rows]

    def ack_leaves(self, buy_in_ids):
        """Central closed these buy-ins: the entries are no longer needed."""
        with self._connection() as conn:
            conn.executemany('DELETE FROM pending_leave WHERE buy_in_id = ?',
                             [(buy_in_id,) for buy_in_id in buy_in_ids])
