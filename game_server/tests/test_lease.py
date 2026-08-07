"""Holder-side lease expiry: a game server that cannot reach central stops
staking its players' balances *before* central may hand their seats to another
server. This pins both halves — the client's expiry rule, and the game loop
freezing between rounds instead of playing on.
"""
import os
import time


import game_server.loop as loop_module
from game_server.central_client import CentralClient
from game_server.config import LEASE_TIMEOUT
from game_server.game.model import Table, User
from game_server.tests.test_game_loop import loop_env  # noqa: F401  (fixture)


class FakeCentral:
    """Stands in for the real client: the lease is flipped by hand."""
    def __init__(self, valid=True):
        self.valid = valid

    def lease_valid(self):
        return self.valid


def test_lease_expires_when_central_goes_silent():
    client = CentralClient('http://central.invalid')
    assert client.lease_valid()  # registration at boot is the first contact

    client._last_contact -= LEASE_TIMEOUT + 1
    assert not client.lease_valid()


def test_lease_timeout_is_shorter_than_the_seat_takeover():
    """The safety inequality: this server must give up before central gives
    the same players away, or both would consider themselves entitled to stake
    the same balance.

    The inequality is only meaningful because the lease is checked at the
    instant stakes are committed (the deal) — see the test below. Checked only
    once per round, it would say nothing: a round is far longer than the gap
    between the two constants.
    """
    from central_server.config import SEAT_TAKEOVER_TTL
    assert LEASE_TIMEOUT < SEAT_TAKEOVER_TTL


def test_a_lease_lost_during_the_betting_window_cancels_before_the_deal(loop_env, monkeypatch):  # noqa: F811
    """The betting window is tens of seconds long, so a lease still valid when
    the round opened can be dead by the time the cards would go down. Bets are
    not stakes until the deal, so the round is cancelled and nothing is staked.
    """
    sio, box = loop_env
    central = FakeCentral(valid=True)
    monkeypatch.setattr(loop_module, 'client', central)
    monkeypatch.setattr(loop_module, 'LEASE_CHECK_SECONDS', 0.05)

    table = Table('t-lease-window')
    table.add_user(User('u1', 1000))
    table.add_user(User('u2', 1000))

    gl = loop_module.GameLoop(table)
    gl.start()
    try:
        sio.wait_for('place_bets')          # lease was valid: the round opened
        game = table.game
        for u in list(game.active_users):
            game.place_bet(u, 10)

        central.valid = False               # the link drops mid-window
        gl.bets_done_event.set()

        # No cards are dealt and no result is settled: nothing was staked.
        sio.wait_for('lease_expired')
        assert sio.all('initial_cards') == []
        assert box.enqueued == []
    finally:
        for u in list(table.users):
            table.remove_user(u)
        gl.bets_done_event.set()
        gl.join(timeout=3)


def test_frozen_table_starts_no_round_and_resumes_on_its_own(loop_env, monkeypatch):  # noqa: F811
    sio, _ = loop_env
    central = FakeCentral(valid=False)
    monkeypatch.setattr(loop_module, 'client', central)
    monkeypatch.setattr(loop_module, 'LEASE_CHECK_SECONDS', 0.05)

    table = Table('t-lease')
    table.add_user(User('u1', 1000))
    table.add_user(User('u2', 1000))

    gl = loop_module.GameLoop(table)
    gl.start()
    try:
        sio.wait_for('lease_expired')
        time.sleep(0.2)
        # No betting is opened while the balances cannot be settled.
        assert sio.all('place_bets') == []

        central.valid = True  # the link heals
        sio.wait_for('lease_restored')
        sio.wait_for('place_bets')  # play resumes by itself, nobody was kicked
    finally:
        for u in list(table.users):
            table.remove_user(u)
        gl.bets_done_event.set()
        gl.join(timeout=3)
