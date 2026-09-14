import time
from central_server import db
from central_server.config import SEAT_GRACE, SEAT_TAKEOVER

USERNAME_1 = 'user1'
USERNAME_2 = 'user2'

def _add_server(session_db, seen_ago=0):
    server_id = session_db.register_server('localhost', 8000, 10)
    with session_db.SessionLocal() as session:
        session.get(session_db.GameServer, server_id).last_seen = time.time() - seen_ago
        session.commit()
    return server_id

def _age_seat(session_db, username, seconds):
    with session_db.SessionLocal() as session:
        session.get(session_db.Seat, username).since = time.time() - seconds
        session.commit()


def test_refuse_second_dispatch_to_another_server(session_db):
    first, second = _add_server(session_db), _add_server(session_db)

    assert db.take_seat(USERNAME_1, first)
    assert not db.take_seat(USERNAME_1, second)

def test_allow_dispatch_to_same_server(session_db):
    server = _add_server(session_db)

    assert db.take_seat(USERNAME_1, server)
    assert db.take_seat(USERNAME_1, server)


def test_takeover_seat_from_dead_server(session_db):
    dead, alive = _add_server(session_db, seen_ago=SEAT_TAKEOVER + 5), _add_server(session_db)

    assert db.take_seat(USERNAME_1, dead)
    assert db.take_seat(USERNAME_1, alive)


def test_heartbeat_releases_player_who_left(session_db):
    server, other = _add_server(session_db), _add_server(session_db)
    db.take_seat(USERNAME_1, server)
    # needed because otherwise the user appears as not yet seated after dispatch
    _age_seat(session_db, USERNAME_1, SEAT_GRACE + 1)

    db.update_heartbeat(server, [USERNAME_2])

    other = _add_server(session_db)
    assert db.take_seat(USERNAME_1, other)

def test_heartbeat_spares_users_in_seat_grace(session_db):
    server, other = _add_server(session_db), _add_server(session_db)
    db.take_seat(USERNAME_1, server)

    db.update_heartbeat(server, [])

    assert not db.take_seat(USERNAME_1, other)
