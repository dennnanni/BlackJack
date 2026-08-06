from game_server.game.model import Card, Deck, Game, User


def test_game_betting_and_result():
    """End to end: a bet, a settled hand, the Result rows and the balance."""
    user = User("Charlie", 100)
    game = Game([user], Deck())

    game.place_bet(user, 20)
    assert game.bets[user] == 20

    user.add_card(Card("10", "Spades"))
    user.add_card(Card("9", "Clubs"))
    game.add_dealer_card(Card("8", "Diamonds"))
    game.add_dealer_card(Card("7", "Hearts"))

    results = game.determine_result()
    assert results[0].username == "Charlie"
    assert results[0].balance_difference == 20
    assert user.balance == 120
