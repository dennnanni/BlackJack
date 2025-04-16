from game_server.src.model.game_structures import Card, Hand, Game, User
import pytest

DEFAULT_SUIT = 'Hearts'

@pytest.mark.parametrize("hand,expected", [
    ([Card('J', DEFAULT_SUIT), Card('K', DEFAULT_SUIT)], 20),
    ([Card('A', DEFAULT_SUIT), Card('A', DEFAULT_SUIT), Card('9', DEFAULT_SUIT)], 21),
    ([Card('Q', DEFAULT_SUIT), Card('J', DEFAULT_SUIT), Card('2', DEFAULT_SUIT)], 22),
])
def test_hand_value(hand, expected):
    assert Hand.get_hand_value(hand) == expected
    
def test_is_blackjack():
    blackjack_hand = [Card('A', DEFAULT_SUIT), Card('J', DEFAULT_SUIT)]
    non_blackjack_hand = [Card('10', DEFAULT_SUIT), Card('J', DEFAULT_SUIT)]
    
    assert Hand.is_blackjack(blackjack_hand) == True
    assert Hand.is_blackjack(non_blackjack_hand) == False

def test_is_busted():
    busted_hand = [Card('J', DEFAULT_SUIT), Card('J', DEFAULT_SUIT), Card('3', DEFAULT_SUIT)]
    non_busted_hand = [Card('J', DEFAULT_SUIT), Card('9', DEFAULT_SUIT)]
    
    assert Hand.is_busted(busted_hand) == True
    assert Hand.is_busted(non_busted_hand) == False
    
def test_has_ace():
    hand_with_ace = [Card('A', DEFAULT_SUIT), Card('J', DEFAULT_SUIT)]
    hand_without_ace = [Card('10', DEFAULT_SUIT), Card('J', DEFAULT_SUIT)]
    
    assert Hand.has_ace(hand_with_ace) == True
    assert Hand.has_ace(hand_without_ace) == False
    
def test_determine_difference():
    users = [User("User1", 200), User("User2", 200), User("User3", 200)]
    game = Game(users)
    
    game.place_bet(users[0], 100)
    game.place_bet(users[1], 200)
    game.place_bet(users[2], 100)
    
    # Simulate a game state
    users[0].add_card(Card('A', DEFAULT_SUIT))
    users[0].add_card(Card('J', DEFAULT_SUIT))
    users[1].add_card(Card('Q', DEFAULT_SUIT))
    users[1].add_card(Card('J', DEFAULT_SUIT))
    users[2].add_card(Card('9', DEFAULT_SUIT))
    users[2].add_card(Card('8', DEFAULT_SUIT))
    users[2].add_card(Card('K', DEFAULT_SUIT))
    
    game.add_dealer_card(Card('9', DEFAULT_SUIT)) 
    game.add_dealer_card(Card('8', DEFAULT_SUIT))
    
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
    game.add_dealer_card(Card('2', DEFAULT_SUIT))
    game.add_dealer_card(Card('Q', DEFAULT_SUIT))
    game.add_dealer_card(Card('K', DEFAULT_SUIT))
    with pytest.raises(Exception) as exc_info:
        game.add_dealer_card(Card('K', DEFAULT_SUIT))
    assert str(exc_info.value) == "Dealer cannot take more cards"
    
def test_is_winner():
    user = User("User1", 200)
    game = Game([user])
    
    user.add_card(Card('A', DEFAULT_SUIT))  # Ace
    user.add_card(Card('J', DEFAULT_SUIT))  # 'J'
    game.add_dealer_card(Card('10', DEFAULT_SUIT))  # 10
    game.add_dealer_card(Card('Q', DEFAULT_SUIT))  # 'J'
    assert game._is_winner(user) == True
    
    user.remove_card(Card('A', DEFAULT_SUIT))  # Remove Ace
    assert len(user.get_hand()) == 1  # Check if Ace is removed
    user.add_card(Card('10', DEFAULT_SUIT))  # Add 10
    assert game._is_winner(user) == False