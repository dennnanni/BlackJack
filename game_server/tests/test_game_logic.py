from game_server.src.model.game_structures import Card, Hand
import pytest

@pytest.mark.parametrize("hand,expected", [
    ([Card(9, 0), Card(12, 0)], 20),
    ([Card(0, 0), Card(0, 0), Card(8, 0)], 21),
    ([Card(11, 0), Card(10, 0), Card(1, 0)], 22),
])
def test_hand_value(hand, expected):
    assert Hand.get_hand_value(hand) == expected
    
def test_is_blackjack():
    blackjack_hand = [Card(0, 0), Card(10, 0)]
    non_blackjack_hand = [Card(9, 0), Card(10, 0)]
    
    assert Hand.is_blackjack(blackjack_hand) == True
    assert Hand.is_blackjack(non_blackjack_hand) == False

def test_is_busted():
    busted_hand = [Card(10, 0), Card(10, 0), Card(2, 0)]
    non_busted_hand = [Card(10, 0), Card(8, 0)]
    
    assert Hand.is_busted(busted_hand) == True
    assert Hand.is_busted(non_busted_hand) == False
    
def test_has_ace():
    hand_with_ace = [Card(11, 0), Card(10, 0)]
    hand_without_ace = [Card(9, 0), Card(10, 0)]
    
    assert Hand.has_ace(hand_with_ace) == True
    assert Hand.has_ace(hand_without_ace) == False