import time

from central_server import db
from central_server.config import HEARTBEAT


def _pick():
    live = db.get_alive_servers()
    return live[0] if live else None


def _add_server(session_db, seats, capacity=10, seen_ago=0):
    server_id = session_db.register_server('localhost', 8000, capacity)
    with session_db.SessionLocal() as session:
        server = session.get(session_db.GameServer, server_id)
        server.last_seen = time.time() - seen_ago
        for i in range(seats):
            session.add(session_db.Seat(username=f'user{server_id}-{i}',
                                        server_id=server_id, since=time.time()))
        session.commit()
    return server_id


def test_dispatcher_prefers_least_loaded_live_server(session_db):
    _add_server(session_db, seats=5)
    expected = _add_server(session_db, seats=2)
    _add_server(session_db, seats=0, seen_ago=HEARTBEAT + 5)  # stale: dead server

    assert _pick().id == expected


def test_dispatcher_skips_full_servers(session_db):
    _add_server(session_db, seats=3, capacity=3)  # full
    expected = _add_server(session_db, seats=9, capacity=10)

    assert _pick().id == expected


def test_dispatcher_returns_none_when_no_server_is_eligible(session_db):
    assert _pick() is None

    _add_server(session_db, seats=0, seen_ago=HEARTBEAT + 5)
    assert _pick() is None


def test_stale_server_returns_to_dispatch_when_it_heartbeats_again(session_db):
    stale_id = _add_server(session_db, seats=0, seen_ago=HEARTBEAT + 5)
    assert _pick() is None

    session_db.update_heartbeat(stale_id, [])
    assert _pick().id == stale_id


def test_play_moves_on_when_the_chosen_server_filled_up(session_db, monkeypatch):
    from central_server import auth
    from central_server.app import create_app

    full = session_db.register_server('localhost', 8000, 1)
    free = session_db.register_server('localhost', 8001, 10)
    db.take_seat('other', full)
    hashed, salt = auth.generate_hashed_password('pw')
    session_db.add_user('user', hashed, salt, 1000)
    # the list was read before a concurrent dispatch filled the first server
    stale_list = [session_db.GameServer(id=full, host='localhost', port=8000),
                  session_db.GameServer(id=free, host='localhost', port=8001)]
    monkeypatch.setattr(db, 'get_alive_servers', lambda: stale_list)

    client = create_app().test_client()
    client.post('/login', data={'username': 'user', 'password': 'pw'})
    response = client.post('/play', data={'buy_in': 100})

    assert 'localhost:8001/join' in response.get_data(as_text=True)
    assert float(session_db.get_user('user').balance) == 900.0
