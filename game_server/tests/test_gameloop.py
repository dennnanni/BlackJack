import pytest
from unittest.mock import patch, MagicMock
from src.model.game_structures import Table, User
from src.game_loop import GameLoop

@pytest.fixture
def table_with_users():
    users = [
        User(username="Alice", balance=1000),
        User(username="Bob", balance=1000),
        User(username="Carol", balance=1000)
    ]
    table = Table(id=1)
    for user in users:
        table.add_user(user)
    return table

@patch("src.game_loop.socketio.emit")
@patch("src.utils.update_user_balance")
def test_game_loop_starts_and_completes(mock_update_balance, mock_emit, table_with_users):
    table = table_with_users

    # Crea il GameLoop e avvia il thread
    game_loop = GameLoop(table)
    game_loop.bets_done_event.set()    # Simula che le puntate siano state fatte
    game_loop.actions_done_event.set() # Simula che le azioni siano state fatte

    game_loop.start()
    game_loop.join(timeout=5)

    assert not game_loop.running  # Deve essere terminato
    assert table.get_game() is None  # Il gioco è stato pulito
    assert mock_emit.call_count > 0  # Sono stati emessi eventi
    assert mock_update_balance.call_count > 0  # Bilanci aggiornati

@patch("src.game_loop.socketio.emit")
def test_game_loop_not_enough_users(mock_emit):
    table = Table(id=2)
    table.add_user(User(username="Solo", sid="sid1", balance=500))

    game_loop = GameLoop(table)
    game_loop.start()
    game_loop.join(timeout=3)

    assert not game_loop.running
    assert table.get_game() is None
    # Non dovrebbe aver emesso eventi di gioco
    emitted_events = [call[0][0] for call in mock_emit.call_args_list]
    assert 'game_starting' not in emitted_events
