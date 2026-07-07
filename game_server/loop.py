"""Round state machine: one GameLoop thread drives the rounds of one table."""
from threading import Event, Thread

from game_server.app import socketio
from game_server.central_client import client
from game_server.game.model import Deck, Game, Hand

BET_WINDOW_SECONDS = 35
ACTION_WINDOW_SECONDS = 60


class GameLoop(Thread):
    def __init__(self, table):
        super().__init__(daemon=True)
        self.table = table
        self.running = True
        self.bets_done_event = Event()
        self.actions_done_event = Event()
        self.room_id = f"table-{table.get_table_id()}"

    def run(self):
        while self.table.is_ready_to_start():
            socketio.emit('game_starting', {'table': self.table.get_table_id()}, to=self.room_id)
            deck = Deck()
            game = Game(self.table.get_users()[:], deck)
            self.table.set_game(game)

            # Betting phase
            socketio.emit('place_bets', {'table': self.table.get_table_id()}, to=self.room_id)
            self.bets_done_event.wait(timeout=BET_WINDOW_SECONDS)
            for user in self.table.get_users():
                if not game.get_userbet(user):
                    # No bet placed in time -> excluded from this round
                    game.remove_active_user(user)

            if not game.get_bet():
                socketio.emit('no_players_bet', {'table': self.table.get_table_id()}, to=self.room_id)
                self.table.clear_game()
                break

            # Initial deal
            for user in game.get_active_users():
                user.clear_hand()
                user.add_card(deck.draw_card())
                user.add_card(deck.draw_card())

            socketio.emit('initial_cards', {
                'table': self.table.get_table_id(),
                'hands': {
                    u.get_username(): [str(c) for c in u.get_hand()]
                    for u in game.get_active_users()
                }
            }, to=self.room_id)

            # Player actions (hit/stand/double) arrive via Socket.IO events
            self.actions_done_event.wait(ACTION_WINDOW_SECONDS)

            # Whoever did not finish acting stands automatically
            for user in game.get_active_users()[:]:
                game.player_stand(user)
                socketio.emit('player_auto_stand', {
                    'user': user.get_username(),
                    'table': self.table.get_table_id()
                }, to=self.room_id)

            # Dealer turn
            while Hand.get_hand_value(game.get_dealer_hand()) < Game.DEALER_STAND_VALUE:
                game.add_dealer_card(deck.draw_card())

            socketio.emit('dealer_done', {
                'cards': [str(c) for c in game.get_dealer_hand()]
            }, to=self.room_id)

            # Results: apply locally, notify the room, report to central
            results = game.determine_result()
            socketio.emit('round_results', {
                'results': [r.to_dict() for r in results]
            }, to=self.room_id)

            client.send_results(results)
            self.table.clear_game()
            self.bets_done_event.clear()
            self.actions_done_event.clear()

        self.running = False
