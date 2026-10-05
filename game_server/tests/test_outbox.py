import pytest

from game_server.outbox import Outbox
from shared.messages import Result


@pytest.fixture
def path(tmp_path):
    return str(tmp_path / 'outbox.db')


def _results(username='alice', buy_in_id='b-1', diff=10.0):
    return [Result(username, buy_in_id, diff)]


def test_undelivered_rounds_survive_a_restart(path):
    Outbox(path).enqueue('r-1', _results(diff=-25.0))

    after_crash = Outbox(path)
    [(round_id, results)] = after_crash.pending()
    assert round_id == 'r-1'
    assert results == _results(diff=-25.0)


def test_pending_leaves_and_seats_survive_a_restart(path):
    box = Outbox(path)
    box.seat('b-seated')
    box.enqueue_leave('b-left')

    after_crash = Outbox(path)
    assert after_crash.pending_leaves() == ['b-left']
    assert after_crash.abandon_seats() == ['b-seated']


def test_server_id_survives_a_restart(path):
    box = Outbox(path)
    assert box.server_id() is None
    box.save_server_id(3)
    box.save_server_id(4)# a re-registration replaces it, never adds a row

    assert Outbox(path).server_id() == 4


def test_the_same_round_is_queued_once(path):
    """Enqueuing a round again must not make us
    send it twice: the first payload wins."""
    box = Outbox(path)
    box.enqueue('r-1', _results(diff=10.0))
    box.enqueue('r-1', _results(diff=999.0))

    assert box.pending() == [('r-1', _results(diff=10.0))]


def test_rounds_are_delivered_oldest_first(path):
    box = Outbox(path)
    for round_id in ('r-1', 'r-2', 'r-3'):
        box.enqueue(round_id, _results())

    ids = []
    for round_id, _ in box.pending():
        ids.append(round_id)

    assert ids == ['r-1', 'r-2', 'r-3']


def test_ack_removes_only_that_round(path):
    box = Outbox(path)
    box.enqueue('r-1', _results())
    box.enqueue('r-2', _results())
    box.ack('r-1')

    ids = []
    for round_id, _ in box.pending():
        ids.append(round_id)
    assert ids == ['r-2']
    assert not box.is_empty()


def test_leaving_releases_the_seat(path):
    box = Outbox(path)
    box.seat('b-1')
    box.enqueue_leave('b-1')

    assert box.pending_leaves() == ['b-1']
    assert box.abandon_seats() == []
    assert box.pending_leaves() == ['b-1']


def test_abandon_seats_turns_every_seat_into_a_leave_once(path):
    box = Outbox(path)
    box.seat('b-1')
    box.seat('b-2')
    box.seat('b-1')# seating twice holds it once

    assert sorted(box.abandon_seats()) == ['b-1', 'b-2']
    assert sorted(box.pending_leaves()) == ['b-1', 'b-2']
    # A second restart has nothing left to abandon and queues nothing twice.
    assert box.abandon_seats() == []
    assert sorted(box.pending_leaves()) == ['b-1', 'b-2']


def test_ack_leaves_removes_only_the_settled_ones(path):
    box = Outbox(path)
    for buy_in_id in ('b-1', 'b-2', 'b-3'):
        box.enqueue_leave(buy_in_id)
    box.ack_leaves(['b-1', 'b-3'])

    assert box.pending_leaves() == ['b-2']


def test_is_empty_needs_both_rounds_and_leaves_delivered(path):
    box = Outbox(path)
    assert box.is_empty()

    box.enqueue('r-1', _results())
    box.enqueue_leave('b-1')
    box.ack('r-1')
    assert not box.is_empty()

    box.ack_leaves(['b-1'])
    assert box.is_empty()


