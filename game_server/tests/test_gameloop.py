import unittest
from unittest.mock import MagicMock, patch
from threading import Event
from src.game_loop import GameLoop
from src.model.game_structures import User, Table, Game, Card, Deck, Hand

class TestGameLoop(unittest.TestCase):
    def setUp(self):
        # Mock degli utenti
        self.user1 = User("user1", 100)
        self.user2 = User("user2", 100)
        self.user3 = User("user3", 100)

        # Mock della tabella
        self.table = Table("test-table")
        self.table.add_user(self.user1)
        self.table.add_user(self.user2)
        self.table.add_user(self.user3)
        
        # Mock della funzione is_ready_to_start
        self.table.is_ready_to_start = MagicMock(return_value=True)

        # GameLoop
        self.loop = GameLoop(self.table)
        
        # Finta partita
        self.mock_game = Game([self.user1, self.user2, self.user3], Deck())
        self.table.set_game(self.mock_game)

    @patch("src.game_loop.socketio.emit")
    @patch("src.game_loop.update_user_balance")
    def test_game_loop_basic_flow(self, mock_update_balance, mock_emit):
        # Mock delle puntate
        self.mock_game.place_bet(self.user1, 10)
        self.mock_game.place_bet(self.user2, 20)
        self.mock_game.place_bet(self.user3, 30)
        
        # Finta mano
        self.user1.add_card(Card("10", "Hearts"))
        self.user1.add_card(Card("9", "Spades"))
        
        self.user2.add_card(Card("8", "Hearts"))
        self.user2.add_card(Card("7", "Clubs"))
        
        self.user3.add_card(Card("J", "Diamonds"))
        self.user3.add_card(Card("8", "Hearts"))
        
        # Dealer
        self.mock_game.add_dealer_card(Card("6", "Hearts"))
        self.mock_game.add_dealer_card(Card("10", "Spades"))

        # Trigger eventi manualmente
        self.loop.bets_done_event.set()
        self.loop.actions_done_event.set()

        # Avvia il game loop
        self.loop.run()

        # Verifica che la funzione socketio.emit sia stata chiamata almeno una volta
        self.assertTrue(mock_emit.called)
        
        # Verifica che update_user_balance sia stato chiamato per ciascun utente
        self.assertEqual(mock_update_balance.call_count, 3)

        # Verifica che la partita sia stata pulita
        self.assertIsNone(self.table.get_game())
        
    def tearDown(self):
        self.loop.running = False
