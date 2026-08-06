"""The hand-evaluation rules. This is the only file that tests `Hand`."""
import pytest

from game_server.game.model import Card, Hand

S = 'Spades'


@pytest.mark.parametrize("hand,expected", [
    ([Card('10', S), Card('9', S)], 19),                   # no ace
    ([Card('A', S), Card('9', S)], 20),                    # ace as 11
    ([Card('A', S), Card('K', S), Card('5', S)], 16),      # ace drops to 1
    ([Card('A', S), Card('A', S), Card('9', S)], 21),      # only one ace drops
    ([Card('J', S), Card('K', S)], 20),
    ([Card('Q', S), Card('J', S), Card('2', S)], 22),
])
def test_hand_value(hand, expected):
    assert Hand.get_hand_value(hand) == expected


@pytest.mark.parametrize("hand,busted", [
    ([Card('J', S), Card('J', S), Card('3', S)], True),
    ([Card('K', S), Card('Q', S), Card('5', S)], True),
    ([Card('J', S), Card('9', S)], False),
])
def test_is_busted(hand, busted):
    assert Hand.is_busted(hand) is busted


@pytest.mark.parametrize("hand,blackjack", [
    ([Card('A', S), Card('J', S)], True),
    ([Card('A', S), Card('K', S)], True),
    ([Card('10', S), Card('J', S)], False),                # 20, not 21
    ([Card('7', S), Card('7', S), Card('7', S)], False),   # 21, but three cards
])
def test_is_blackjack(hand, blackjack):
    assert Hand.is_blackjack(hand) is blackjack


def test_has_ace():
    assert Hand.has_ace([Card('A', S), Card('J', S)])
    assert not Hand.has_ace([Card('10', S), Card('J', S)])
