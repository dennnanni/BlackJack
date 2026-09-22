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
            conn.execute('CREATE TABLE IF NOT EXISTS seated ('
                         'buy_in_id TEXT PRIMARY KEY,'
                         'created_at REAL NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS identity ('
                         'id INTEGER PRIMARY KEY CHECK (id = 0),'
                         'server_id INTEGER NOT NULL)')

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.path)
        try:
            with conn:  # one transaction, committed on success
                yield conn
        finally:
            conn.close()

    def server_id(self):
        """Our id at central, None until we first registered."""
        with self._connection() as conn:
            row = conn.execute('SELECT server_id FROM identity').fetchone()
        return row[0] if row else None

    def save_server_id(self, server_id):
        with self._connection() as conn:
            conn.execute('INSERT OR REPLACE INTO identity VALUES (0, ?)', (server_id,))

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

    def seat(self, buy_in_id):
        """A player sat down with this buy-in."""
        with self._connection() as conn:
            conn.execute('INSERT OR IGNORE INTO seated VALUES (?, ?)',
                         (buy_in_id, time.time()))

    def enqueue_leave(self, buy_in_id):
        """A player left the table: central must close their buy-in."""
        with self._connection() as conn:
            conn.execute('DELETE FROM seated WHERE buy_in_id = ?', (buy_in_id,))
            conn.execute('INSERT OR IGNORE INTO pending_leave VALUES (?, ?)',
                         (buy_in_id, time.time()))

    def abandon_seats(self):
        """Turn every seated buy-in into a pending leave. Used at startup,
            when whoever was seated before the restart is gone."""
        with self._connection() as conn:
            rows = conn.execute('SELECT buy_in_id FROM seated').fetchall()
            conn.execute('INSERT OR IGNORE INTO pending_leave '
                         'SELECT buy_in_id, ? FROM seated', (time.time(),))
            conn.execute('DELETE FROM seated')
        return [buy_in_id for (buy_in_id,) in rows]

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
