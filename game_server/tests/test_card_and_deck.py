from game_server.game.model import Card, Deck

def test_card_value():
    card = Card("K", "Hearts")
    assert card.value == 10
    card = Card("A", "Hearts")
    assert card.value == 11

def test_deck_draw_card():
    deck = Deck()
    card = deck.draw_card()
    assert isinstance(card, Card)
    assert len(deck.cards) == 51
