from src.model.game_structures import Card, Hand

def test_hand_value_no_ace():
    hand = [Card("10", "Spades"), Card("9", "Clubs")]
    assert Hand.get_hand_value(hand) == 19

def test_hand_value_with_ace():
    hand = [Card("A", "Hearts"), Card("9", "Clubs")]
    assert Hand.get_hand_value(hand) == 20

def test_is_busted():
    hand = [Card("K", "Spades"), Card("Q", "Clubs"), Card("5", "Diamonds")]
    assert Hand.is_busted(hand)

def test_is_blackjack():
    hand = [Card("A", "Spades"), Card("K", "Hearts")]
    assert Hand.is_blackjack(hand)

def test_ace_value():
    hand = [Card("A", "Spades"), Card("K", "Hearts"), Card("5", "Spades")]
    assert Hand.get_hand_value(hand) == 16
    