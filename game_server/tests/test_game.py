from src.model.game_structures import User, Game, Deck, Card, Hand

def test_game_betting_and_result():
    user = User("Charlie", 100)
    deck = Deck()
    game = Game([user], deck)

    game.place_bet(user, 20)
    assert game.get_bet(user) == 20

    user.add_card(Card("10", "Spades"))
    user.add_card(Card("9", "Clubs"))
    game.add_dealer_card(Card("8", "Diamonds"))
    game.add_dealer_card(Card("7", "Hearts"))

    results = game.determine_result()
    assert results[0].username == "Charlie"
    assert results[0].balanceDifference == 20
    assert user.get_balance() == 120
