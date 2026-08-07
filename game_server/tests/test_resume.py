"""A page reload must not cost a player their round.

The socket handler replays the table's live state to the client that just
(re)connected, so what the browser missed while it was reloading is exactly
what it is told on arrival.
"""
import os

os.environ.setdefault('SHARED_SECRET', 'test-secret')
os.environ['OUTBOX_PATH'] = os.path.join(
    os.environ.get('PYTEST_TMPDIR', '/tmp'), 'test_outbox_resume.db')

import pytest

import game_server.events as events
from game_server.game.model import Card, Deck, Game, Table, User


class FakeLoop:
    def __init__(self, betting_open=False, current_player=None):
        self.betting_open = betting_open
        self.current_player = current_player


@pytest.fixture
def table(monkeypatch):
    """A table with a round in progress and alice's client just reconnected."""
    emitted = []
    monkeypatch.setattr(events, 'emit', lambda e, d=None, **kw: emitted.append((e, d)))
    monkeypatch.setattr(events.client, 'lease_valid', lambda: True)

    alice = User('alice', 1000)
    table = Table('t1')
    table.add_user(alice)
    table.game = Game([alice], Deck())
    alice.add_card(Card('10', 'Spades'))
    alice.add_card(Card('7', 'Hearts'))
    events.user_map['alice'] = alice
    events.table_manager.tables.append(table)
    events.table_manager.user_table_map['alice'] = table
    yield table, alice, emitted
    events.user_map.pop('alice', None)
    events.table_game_map.pop('t1', None)
    events.table_manager.tables.remove(table)
    events.table_manager.user_table_map.pop('alice', None)
    events.absent.discard('alice')


def _names(emitted):
    return [e for e, _ in emitted]


def test_reload_during_the_betting_window_can_still_bet(table):
    t, alice, emitted = table
    events.table_game_map['t1'] = FakeLoop(betting_open=True)

    events._resume(t, 'alice')

    assert 'place_bets' in _names(emitted)


def test_reload_after_betting_does_not_reopen_the_bet(table):
    t, alice, emitted = table
    t.game.place_bet(alice, 10)
    events.table_game_map['t1'] = FakeLoop(betting_open=True)

    events._resume(t, 'alice')

    assert 'place_bets' not in _names(emitted)


def test_reload_on_your_turn_gets_the_turn_back(table):
    t, alice, emitted = table
    events.table_game_map['t1'] = FakeLoop(current_player=alice)

    events._resume(t, 'alice')

    hands = dict(emitted)['initial_cards']['hands']
    assert hands['alice'] == ['10♠', '7♥']          # the board is restored...
    assert dict(emitted)['turn_started']['user'] == 'alice'  # ...and the buttons

def test_an_observer_is_not_invited_to_bet(table):
    t, alice, emitted = table
    bob = User('bob', 1000)          # arrived mid-round: not in this game
    t.add_observer(bob)
    events.user_map['bob'] = bob
    events.table_game_map['t1'] = FakeLoop(betting_open=True)

    events._resume(t, 'bob')

    assert 'place_bets' not in _names(emitted)
    events.user_map.pop('bob')


def test_a_player_whose_tab_is_gone_is_unseated_after_the_round(table):
    t, alice, emitted = table
    events.absent.add('alice')

    events.reap_absent(t)

    assert 'alice' not in events.user_map
    assert alice not in t.users
    assert events.last_balance['alice'] == 1000   # kept for a later reload
    events.last_balance.pop('alice')


def test_a_player_who_reconnected_keeps_their_seat(table):
    t, alice, emitted = table
    events.absent.add('alice')
    events.absent.discard('alice')   # what the 'join' handler does on reload

    events.reap_absent(t)

    assert events.user_map['alice'] is alice


def test_reload_while_the_lease_is_expired_shows_the_freeze(table, monkeypatch):
    t, alice, emitted = table
    monkeypatch.setattr(events.client, 'lease_valid', lambda: False)
    events.table_game_map['t1'] = FakeLoop(current_player=alice)

    events._resume(t, 'alice')

    assert 'lease_expired' in _names(emitted)
