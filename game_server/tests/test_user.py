from src.model.game_structures import User, Card

def test_user_creation():
    user = User("Alice", 100)
    assert user.get_username() == "Alice"
    assert user.get_balance() == 100
    assert user.get_hand() == []

def test_user_hand():
    user = User("Bob", 50)
    card = Card("A", "Spades")
    user.add_card(card)
    assert user.get_hand() == [card]
    card2 = Card("Q", "Spades")
    user.add_card(card2)
    assert user.get_hand() == [card, card2]
    user.remove_card(card2)
    assert user.get_hand() == [card]

def test_update_balance():
    user = User("Eve", 200)
    user.update_balance(-50)
    assert user.get_balance() == 150
