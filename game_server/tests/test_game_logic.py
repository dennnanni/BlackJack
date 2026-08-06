"""Round rules: betting limits, the dealer stand rule, and who wins what.
Hand evaluation itself is covered in test_hand.py."""
import pytest

from game_server.game.model import Card, Deck, Game, User

DEFAULT_SUIT = 'Hearts'


def test_determine_difference():
    users = [User("User1", 200), User("User2", 200), User("User3", 200)]
    game = Game(users, Deck())

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

    assert game._determine_difference(users[0]) == 100   # User1 has blackjack
    assert game._determine_difference(users[1]) == 200   # User2 wins
    assert game._determine_difference(users[2]) == -100  # User3 is busted


def test_user_cannot_place_bet_more_than_balance():
    user = User("User1", 200)
    game = Game([user], Deck())
    with pytest.raises(ValueError) as exc_info:
        game.place_bet(user, 300)
    assert str(exc_info.value) == "Bet exceeds user's balance"


def test_dealer_cannot_add_more_cards():
    game = Game([User("User1", 200)], Deck())
    game.add_dealer_card(Card('2', DEFAULT_SUIT))
    game.add_dealer_card(Card('Q', DEFAULT_SUIT))
    game.add_dealer_card(Card('K', DEFAULT_SUIT))
    with pytest.raises(Exception) as exc_info:
        game.add_dealer_card(Card('K', DEFAULT_SUIT))
    assert str(exc_info.value) == "Dealer cannot take more cards"


def test_blackjack_beats_a_plain_twenty():
    user = User("User1", 200)
    game = Game([user], Deck())

    user.add_card(Card('A', DEFAULT_SUIT))
    user.add_card(Card('J', DEFAULT_SUIT))         # natural blackjack
    game.add_dealer_card(Card('10', DEFAULT_SUIT))
    game.add_dealer_card(Card('Q', DEFAULT_SUIT))  # 20
    assert game._is_winner(user) is True


def test_twenty_does_not_beat_dealer_twenty():
    user = User("User1", 200)
    game = Game([user], Deck())

    user.add_card(Card('10', DEFAULT_SUIT))
    user.add_card(Card('J', DEFAULT_SUIT))         # 20, not a blackjack
    game.add_dealer_card(Card('10', DEFAULT_SUIT))
    game.add_dealer_card(Card('Q', DEFAULT_SUIT))  # 20
    assert game._is_winner(user) is False


def test_player_below_dealer_loses_bet():
    user = User("User1", 200)
    game = Game([user], Deck())
    game.place_bet(user, 50)

    user.add_card(Card('10', DEFAULT_SUIT))
    user.add_card(Card('5', DEFAULT_SUIT))         # 15
    game.add_dealer_card(Card('10', DEFAULT_SUIT))
    game.add_dealer_card(Card('9', DEFAULT_SUIT))  # 19

    assert game._determine_difference(user) == -50


def test_player_wins_when_dealer_busts():
    user = User("User1", 200)
    game = Game([user], Deck())
    game.place_bet(user, 50)

    user.add_card(Card('10', DEFAULT_SUIT))
    user.add_card(Card('8', DEFAULT_SUIT))         # 18
    game.add_dealer_card(Card('10', DEFAULT_SUIT))
    game.add_dealer_card(Card('6', DEFAULT_SUIT))
    game.add_dealer_card(Card('K', DEFAULT_SUIT))  # 26: busted

    assert game._determine_difference(user) == 50


def test_equal_hands_push():
    user = User("User1", 200)
    game = Game([user], Deck())
    game.place_bet(user, 50)

    user.add_card(Card('10', DEFAULT_SUIT))
    user.add_card(Card('9', DEFAULT_SUIT))         # 19
    game.add_dealer_card(Card('10', DEFAULT_SUIT))
    game.add_dealer_card(Card('9', DEFAULT_SUIT))  # 19

    assert game._determine_difference(user) == 0
