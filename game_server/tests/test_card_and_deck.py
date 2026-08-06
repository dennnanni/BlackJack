"""Cards and the deck they are drawn from. Hand evaluation lives in
test_hand.py."""
import pytest

from game_server.game.model import Card, Deck


def test_card_value():
    assert Card("K", "Hearts").value == 10
    assert Card("A", "Hearts").value == 11


def test_invalid_card_is_rejected():
    with pytest.raises(ValueError):
        Card("15", "Hearts")
    with pytest.raises(ValueError):
        Card("K", "Wands")


def test_deck_is_a_full_shuffled_pack():
    deck = Deck()
    assert len(deck.cards) == 52
    assert len(set(str(c) for c in deck.cards)) == 52  # no duplicates


def test_deck_draw_card():
    deck = Deck()
    card = deck.draw_card()
    assert isinstance(card, Card)
    assert len(deck.cards) == 51
    assert card not in deck.cards


def test_empty_deck_raises():
    deck = Deck()
    deck.cards = []
    with pytest.raises(Exception, match="No cards left"):
        deck.draw_card()
