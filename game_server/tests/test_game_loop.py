"""The GameLoop drives a round turn by turn and starts the next one itself.

Socket.IO and the outbox are faked; the "player" side is simulated the way the
real event handlers do it (place a bet, then stand on your turn). This locks in
the two behaviours the UI depends on: strict one-player-at-a-time turns, and an
automatic next round with no page reload.
"""
import os
import threading
import time

# Redirect the durable outbox to a throwaway file before importing the app.
os.environ.setdefault('SHARED_SECRET', 'test-secret')
os.environ['OUTBOX_PATH'] = os.path.join(
    os.environ.get('PYTEST_TMPDIR', '/tmp'), 'test_outbox_gameloop.db')

import pytest

import game_server.loop as loop_module
from game_server.game.model import Card, Table, User


class FakeSocketIO:
    def __init__(self):
        self._events = []
        self._lock = threading.Lock()

    def emit(self, event, data=None, to=None):
        with self._lock:
            self._events.append((event, data))

    def sleep(self, seconds=0):
        time.sleep(seconds)

    def names(self):
        with self._lock:
            return [e for e, _ in self._events]

    def all(self, name):
        with self._lock:
            return [d for e, d in self._events if e == name]

    def wait_for(self, name, after=0, timeout=3.0):
        """Return the payload of the (after+1)-th `name` emit, waiting for it."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                hits = [d for e, d in self._events if e == name]
            if len(hits) > after:
                return hits[after]
            time.sleep(0.005)
        raise AssertionError(f"'{name}' (occurrence {after}) never emitted; saw {self.names()}")


class FakeOutbox:
    def __init__(self):
        self.enqueued = []

    def enqueue(self, round_id, results):
        self.enqueued.append((round_id, results))


class StackedDeck:
    """A deck that deals a scripted sequence, for deterministic rounds."""
    def __init__(self, cards):
        self._cards = list(cards)

    def draw_card(self):
        return self._cards.pop(0)


def _scripted_round():
    # Deal order is u1,u1,u2,u2 then the dealer draws to 17.
    return StackedDeck([
        Card('10', 'Spades'), Card('7', 'Spades'),    # u1 -> 17
        Card('10', 'Hearts'), Card('8', 'Hearts'),    # u2 -> 18
        Card('10', 'Clubs'), Card('9', 'Clubs'),      # dealer -> 19
    ])


@pytest.fixture
def loop_env(monkeypatch):
    sio = FakeSocketIO()
    box = FakeOutbox()
    monkeypatch.setattr(loop_module, 'socketio', sio)
    monkeypatch.setattr(loop_module, 'outbox', box)
    monkeypatch.setattr(loop_module, 'Deck', _scripted_round)
    # Short windows so a missed wake-up fails fast instead of hanging the suite.
    monkeypatch.setattr(loop_module, 'BET_WINDOW_SECONDS', 2)
    monkeypatch.setattr(loop_module, 'TURN_WINDOW_SECONDS', 2)
    # Drop the pacing delays so the round runs at full speed under test.
    monkeypatch.setattr(loop_module, 'PRE_DEALER_DELAY', 0)
    monkeypatch.setattr(loop_module, 'DEALER_DRAW_DELAY', 0)
    monkeypatch.setattr(loop_module, 'POST_DEALER_DELAY', 0)
    monkeypatch.setattr(loop_module, 'ROUND_RESULT_DELAY', 0)
    return sio, box


def test_turn_based_round_then_automatic_restart(loop_env):
    sio, box = loop_env
    u1, u2 = User('u1', 1000), User('u2', 1000)
    table = Table('t1')
    table.add_user(u1)
    table.add_user(u2)

    gl = loop_module.GameLoop(table)
    gl.start()
    try:
        # Round 1 — betting: both players opt in.
        sio.wait_for('place_bets')
        game = table.game
        for u in list(game.active_users):
            game.place_bet(u, 10)
        gl.bets_done_event.set()

        # u1 gets the table first, alone.
        t1 = sio.wait_for('turn_started', after=0)
        assert t1['user'] == 'u1'
        assert gl.current_player is u1
        game.player_stand(gl.current_player)
        gl.turn_done_event.set()

        # Only after u1 is done does u2's turn begin.
        t2 = sio.wait_for('turn_started', after=1)
        assert t2['user'] == 'u2'
        assert gl.current_player is u2
        game.player_stand(gl.current_player)
        gl.turn_done_event.set()

        # Dealer completes and the round settles — revealed one card at a time.
        dealer = sio.wait_for('dealer_done')
        assert len(dealer['cards']) == 2  # 10 then 9 -> 19
        assert len(sio.all('dealer_card')) == 2  # each card announced on its own
        results = sio.wait_for('round_results')['results']
        assert {r['username'] for r in results} == {'u1', 'u2'}
        assert all(r['balance_difference'] == -10 for r in results)  # 17,18 < 19
        assert len(box.enqueued) == 1  # persisted before it was announced

        # Round 2 begins on its own — no reload, no manual restart.
        sio.wait_for('place_bets', after=1)
    finally:
        # Let the loop end cleanly: empty the table, then release its bet wait.
        for u in list(table.users):
            table.remove_user(u)
        gl.bets_done_event.set()
        gl.join(timeout=3)

    assert not gl.running


def test_a_player_sitting_out_is_not_dealt_in_nor_waited_for(loop_env):
    """The point of sitting out: the others do not sit through the betting
    window waiting for someone who is not playing."""
    import game_server.events as events
    sio, box = loop_env
    player, sitter = User('player', 1000), User('sitter', 1000)
    table = Table('t3')
    table.add_user(player)
    table.add_user(sitter)
    events.sitting_out.add('sitter')

    gl = loop_module.GameLoop(table)
    gl.start()
    try:
        sio.wait_for('place_bets')
        game = table.game
        assert list(game.active_users) == [player]
        game.place_bet(player, 10)
        # Nobody else to wait for, so the table can deal immediately.
        assert game.all_players_have_bet()
        gl.bets_done_event.set()

        hands = sio.wait_for('initial_cards')['hands']
        assert 'sitter' not in hands
        assert [t['user'] for t in sio.all('turn_started')] == ['player']
        game.player_stand(gl.current_player)
        gl.turn_done_event.set()

        results = sio.wait_for('round_results')['results']
        assert [r['username'] for r in results] == ['player']
    finally:
        events.sitting_out.discard('sitter')
        for u in list(table.users):
            table.remove_user(u)
        gl.bets_done_event.set()
        gl.turn_done_event.set()
        gl.join(timeout=3)


def test_a_table_where_everyone_sits_out_idles_instead_of_dealing(loop_env):
    import game_server.events as events
    sio, box = loop_env
    sitter = User('sitter', 1000)
    table = Table('t4')
    table.add_user(sitter)
    events.sitting_out.add('sitter')
    monkeyed = loop_module.IDLE_ROUND_SECONDS
    loop_module.IDLE_ROUND_SECONDS = 0

    gl = loop_module.GameLoop(table)
    gl.start()
    try:
        sio.wait_for('table_idle')
        assert 'place_bets' not in sio.names()
    finally:
        loop_module.IDLE_ROUND_SECONDS = monkeyed
        events.sitting_out.discard('sitter')
        for u in list(table.users):
            table.remove_user(u)
        gl.join(timeout=3)


def test_players_who_do_not_bet_stake_nothing(loop_env):
    sio, box = loop_env
    u1 = User('better', 1000)
    u2 = User('sitter', 1000)
    table = Table('t2')
    table.add_user(u1)
    table.add_user(u2)

    gl = loop_module.GameLoop(table)
    gl.start()
    try:
        sio.wait_for('place_bets')
        game = table.game
        game.place_bet(u1, 25)   # only u1 opts in
        gl.bets_done_event.set()

        # Only the better takes a turn; the sitter is not dealt in.
        t1 = sio.wait_for('turn_started')
        assert t1['user'] == 'better'
        game.player_stand(gl.current_player)
        gl.turn_done_event.set()

        results = sio.wait_for('round_results')['results']
        # The sitter has no result row — they staked nothing.
        assert [r['username'] for r in results] == ['better']
    finally:
        for u in list(table.users):
            table.remove_user(u)
        gl.bets_done_event.set()
        gl.turn_done_event.set()
        gl.join(timeout=3)
