from game_server.game.model import User, Card

def test_user_creation():
    user = User("Alice", 100)
    assert user.username == "Alice"
    assert user.balance == 100
    assert user.hand == []

def test_user_hand():
    user = User("Bob", 50)
    card = Card("A", "Spades")
    user.add_card(card)
    assert user.hand == [card]
    card2 = Card("Q", "Spades")
    user.add_card(card2)
    assert user.hand == [card, card2]

def test_update_balance():
    user = User("Eve", 200)
    user.update_balance(-50)
    assert user.balance == 150
