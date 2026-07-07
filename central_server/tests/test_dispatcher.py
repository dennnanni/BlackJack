"""Failure detection + load-aware dispatch: only servers with fresh
heartbeats and free seats are eligible, and the least loaded one wins.
"""
import time

from central_server import db, dispatcher
from central_server.config import HEARTBEAT_TTL


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
    _add_server(session_db, load=0, seen_ago=HEARTBEAT_TTL + 5)  # stale: dead server

    picked = dispatcher.pick_server()
    assert picked.id == expected


def test_dispatcher_skips_full_servers(session_db):
    _add_server(session_db, load=3, capacity=3)  # full
    expected = _add_server(session_db, load=9, capacity=10)

    picked = dispatcher.pick_server()
    assert picked.id == expected


def test_dispatcher_returns_none_when_no_server_is_eligible(session_db):
    assert dispatcher.pick_server() is None

    _add_server(session_db, load=0, seen_ago=HEARTBEAT_TTL + 5)
    assert dispatcher.pick_server() is None


def test_reaper_scan_reports_stale_and_recovered(session_db):
    from central_server import reaper

    stale_id = _add_server(session_db, load=0, seen_ago=HEARTBEAT_TTL + 5)
    live_id = _add_server(session_db, load=0)

    stale = reaper._scan(set())
    assert stale == {stale_id}

    # The stale server heartbeats again -> reported as recovered
    session_db.heartbeat(stale_id, 0)
    assert reaper._scan(stale) == set()
    assert live_id not in stale
