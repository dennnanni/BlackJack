from game_server.src.model.game_structures import Card, Hand, Game, User
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
    hand_with_ace = [Card(0, 0), Card(10, 0)]
    hand_without_ace = [Card(9, 0), Card(10, 0)]
    
    assert Hand.has_ace(hand_with_ace) == True
    assert Hand.has_ace(hand_without_ace) == False
    
def test_determine_difference():
    users = [User("User1", 200), User("User2", 200), User("User3", 200)]
    game = Game(users)
    
    game.place_bet(users[0], 100)
    game.place_bet(users[1], 200)
    game.place_bet(users[2], 100)
    
    # Simulate a game state
    users[0].add_card(Card(0, 0))
    users[0].add_card(Card(10, 0))
    users[1].add_card(Card(11, 0))
    users[1].add_card(Card(10, 0))
    users[2].add_card(Card(8, 0))
    users[2].add_card(Card(7, 0))
    users[2].add_card(Card(12, 0))
    
    game.add_dealer_card(Card(8, 0)) 
    game.add_dealer_card(Card(7, 0))
    
    assert game._determine_difference(users[0]) == 100  # User1 has blackjack
    assert game._determine_difference(users[1]) == 200   # User2 wins
    assert game._determine_difference(users[2]) == -100     # User3 is busted
    
def test_user_cannot_place_bet_more_than_balance():
    user = User("User1", 200)
    game = Game([user])
    with pytest.raises(ValueError) as exc_info:
        game.place_bet(user, 300)
    assert str(exc_info.value) == "Bet exceeds user's balance"
    
def test_dealer_cannot_add_more_cards():
    game = Game([User("User1", 200)])
    game.add_dealer_card(Card(1, 0))
    game.add_dealer_card(Card(11, 0))
    game.add_dealer_card(Card(12, 0))
    with pytest.raises(Exception) as exc_info:
        game.add_dealer_card(Card(12, 0))
    assert str(exc_info.value) == "Dealer cannot take more cards"
    
def test_is_winner():
    user = User("User1", 200)
    game = Game([user])
    
    user.add_card(Card(0, 0))  # Ace
    user.add_card(Card(10, 0))  # 10
    game.add_dealer_card(Card(8, 0))  # 9
    game.add_dealer_card(Card(11, 0))  # 10
    assert game._is_winner(user) == True
    
    user.remove_card(Card(0, 0))  # Remove Ace
    assert len(user.get_hand()) == 1  # Check if Ace is removed
    user.add_card(Card(8, 0))  # Add 9
    assert game._is_winner(user) == False