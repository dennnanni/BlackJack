import time

from central_server import db
from central_server.config import HEARTBEAT


def _pick():
    live = db.get_alive_servers()
    return min(live, key=lambda s: s.load) if live else None


def _add_server(session_db, load, capacity=10, seen_ago=0):
    server_id = session_db.register_server('localhost', 8000, capacity)
    with session_db.SessionLocal() as session:
        server = session.get(session_db.GameServer, server_id)
        server.load = load
        server.last_seen = time.time() - seen_ago
        session.commit()
    return server_id


def test_dispatcher_prefers_least_loaded_live_server(session_db):
    _add_server(session_db, load=5)
    expected = _add_server(session_db, load=2)
    _add_server(session_db, load=0, seen_ago=HEARTBEAT + 5)  # stale: dead server

    assert _pick().id == expected


def test_dispatcher_skips_full_servers(session_db):
    _add_server(session_db, load=3, capacity=3)  # full
    expected = _add_server(session_db, load=9, capacity=10)

    assert _pick().id == expected


def test_dispatcher_returns_none_when_no_server_is_eligible(session_db):
    assert _pick() is None

    _add_server(session_db, load=0, seen_ago=HEARTBEAT + 5)
    assert _pick() is None


def test_stale_server_returns_to_dispatch_when_it_heartbeats_again(session_db):
    stale_id = _add_server(session_db, load=0, seen_ago=HEARTBEAT + 5)
    assert _pick() is None

    session_db.update_heartbeat(stale_id, [])
    assert _pick().id == stale_id
