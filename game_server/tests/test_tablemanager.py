from src.model.game_structures import User, TableManager

def test_table_assignment_and_retrieval():
    manager = TableManager()
    user1 = User("A", 100)
    user2 = User("B", 100)
    user3 = User("C", 100)
    user4 = User("D", 100)
    user5 = User("E", 100)
    user6 = User("F", 100)

    table1 = manager.assign_user_to_table(user1)
    table2 = manager.assign_user_to_table(user2)
    table3 = manager.assign_user_to_table(user3)
    table4 = manager.assign_user_to_table(user4)
    table5 = manager.assign_user_to_table(user5)
    table6 = manager.assign_user_to_table(user6)

    assert table1 == table2
    assert manager.get_user_table("A") == table1
    assert manager.get_user_table("B") == table1
    assert table1 != table4
    assert table4 == table6
    assert manager.has_user(user5.get_username())
