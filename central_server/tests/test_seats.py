"""One account, one table: the seat table is what stops the same balance
being staked on two game servers at once, and heartbeats are what release a
seat again once the player has left.
"""
import time

from central_server import db
from central_server.config import SEAT_GRACE, SEAT_TAKEOVER_TTL


def _add_server(session_db, seen_ago=0):
    server_id = session_db.register_server('localhost', 8000, 10)
    with session_db.SessionLocal() as session:
        session.get(session_db.GameServer, server_id).last_seen = time.time() - seen_ago
        session.commit()
    return server_id


def _age_seat(session_db, username, seconds):
    """Backdate a seat claim, as if the player had been seated a while."""
    with session_db.SessionLocal() as session:
        session.get(session_db.Seat, username).since = time.time() - seconds
        session.commit()


def test_second_dispatch_to_another_server_is_refused(session_db):
    first, second = _add_server(session_db), _add_server(session_db)

    assert db.take_seat('alice', first, SEAT_TAKEOVER_TTL)
    assert not db.take_seat('alice', second, SEAT_TAKEOVER_TTL)


def test_redispatch_to_the_same_server_is_allowed(session_db):
    server_id = _add_server(session_db)

    assert db.take_seat('alice', server_id, SEAT_TAKEOVER_TTL)
    assert db.take_seat('alice', server_id, SEAT_TAKEOVER_TTL)


def test_seat_of_a_dead_server_is_taken_over(session_db):
    dead = _add_server(session_db, seen_ago=SEAT_TAKEOVER_TTL + 5)
    alive = _add_server(session_db)

    assert db.take_seat('alice', dead, SEAT_TAKEOVER_TTL)
    # The owner is gone, so the player is not locked out of a new table.
    assert db.take_seat('alice', alive, SEAT_TAKEOVER_TTL)


def test_heartbeat_releases_the_seat_of_a_player_who_left(session_db):
    server_id = _add_server(session_db)
    db.take_seat('alice', server_id, SEAT_TAKEOVER_TTL)
    _age_seat(session_db, 'alice', SEAT_GRACE + 1)

    db.heartbeat(server_id, ['bob'])  # alice no longer seated there

    other = _add_server(session_db)
    assert db.take_seat('alice', other, SEAT_TAKEOVER_TTL)


def test_heartbeat_spares_a_seat_the_player_has_not_reached_yet(session_db):
    server_id = _add_server(session_db)
    other = _add_server(session_db)
    db.take_seat('alice', server_id, SEAT_TAKEOVER_TTL)

    # Heartbeat sent while alice is still being redirected: within SEAT_GRACE
    # her claim survives, so the window between dispatch and arrival is not a
    # hole in the exclusion.
    db.heartbeat(server_id, [])

    assert not db.take_seat('alice', other, SEAT_TAKEOVER_TTL)
