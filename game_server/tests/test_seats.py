import threading
import time
from types import SimpleNamespace

import pytest

import game_server.seats as seats
from game_server.game.model import Deck, Game, TableManager, User
from game_server.outbox import Outbox
from shared.messages import Result


class FakeSocketIO:
    def __init__(self):
        self.emitted = []

    def emit(self, event, data=None, to=None):
        self.emitted.append(event)


@pytest.fixture
def box(monkeypatch, tmp_path):
    fresh = Outbox(str(tmp_path / 'outbox.db'))
    monkeypatch.setattr(seats, 'outbox', fresh)
    monkeypatch.setattr(seats, 'socketio', FakeSocketIO())
    monkeypatch.setattr(seats, 'closing', threading.Event())
    monkeypatch.setattr(seats, 'table_manager', TableManager())
    for name, empty in [('user_map', {}), ('table_game_map', {}), ('absent', {}),
                        ('sitting_out', set()), ('seated_buy_ins', set())]:
        monkeypatch.setattr(seats, name, empty)
    return fresh


def _seat(username):
    """What /join and the socket's join do: hold the buy-in, then sit down."""
    buy_in_id = f'b-{username}'
    seats.outbox.seat(buy_in_id)
    seats.seated_buy_ins.add(buy_in_id)
    user = User(username, 100.0, buy_in_id)
    seats.user_map[username] = user
    return user, seats.table_manager.assign_user_to_table(user)


def _start_round(table):
    table.game = Game(table.users[:], Deck())
    return table.game


def test_leaving_between_rounds_closes_the_buy_in_at_once(box):
    _, table = _seat('alice')

    seats.leave_table('alice')

    assert 'alice' not in seats.user_map
    assert table.users == []
    assert box.pending_leaves() == ['b-alice']
    assert box.abandon_seats() == []


def test_leaving_with_a_bet_in_play_closes_the_buy_in_only_after_the_result(box):
    alice, table = _seat('alice')
    game = _start_round(table)
    game.place_bet(alice, 20)

    seats.leave_table('alice')
    assert 'alice' not in seats.user_map
    assert box.pending_leaves() == []

    # what the loop does at the end of the round
    results = game.determine_result()
    box.enqueue('r-1', results)
    seats.close_forfeited_buy_ins(game)

    assert Result('alice', 'b-alice', -20.0) in results# the stake is lost
    assert box.pending_leaves() == ['b-alice']


def test_leaving_mid_round_without_a_stake_closes_the_buy_in_at_once(box):
    _, table = _seat('alice')
    game = _start_round(table)
    _, same_table = _seat('bob')# the round is on: bob only watches
    assert same_table is table and table.observers

    seats.leave_table('alice')
    seats.leave_table('bob')
    assert sorted(box.pending_leaves()) == ['b-alice', 'b-bob']

    box.ack_leaves(['b-alice', 'b-bob'])
    seats.close_forfeited_buy_ins(game)
    assert box.pending_leaves() == []
    assert game.determine_result() == []



@pytest.mark.parametrize('case', ['buy-in already used', 'server restarted',
                                  'join expired', 'server closing', 'no buy-in'])
def test_a_buy_in_takes_a_seat_only_once_and_only_while_valid(box, case):
    """The join token stays valid for minutes: replaying it, or opening the
    table in a second tab, must not seat the same money twice."""
    buy_in_id, join_exp, boot_id = 'b-1', time.time() + 60, seats.BOOT_ID
    assert seats.can_take_seat(buy_in_id, join_exp, boot_id)

    if case == 'buy-in already used':
        seats.seated_buy_ins.add(buy_in_id)
    elif case == 'server restarted':
        boot_id = 'a-previous-boot'
    elif case == 'join expired':
        join_exp = time.time() - 1
    elif case == 'server closing':
        seats.closing.set()
    elif case == 'no buy-in':
        buy_in_id = None

    assert not seats.can_take_seat(buy_in_id, join_exp, boot_id)



def test_absent_players_are_unseated_at_the_end_of_their_tables_round(box):
    _, table = _seat('alice')
    _seat('bob')
    _seat('dave')
    _, other_table = _seat('carol')
    assert other_table is not table
    seats.absent.update({'alice': time.monotonic(), 'carol': time.monotonic()})

    seats.reap_absent(table)

    assert box.pending_leaves() == ['b-alice']
    assert 'alice' not in seats.user_map and 'alice' not in seats.absent
    assert 'carol' in seats.absent
