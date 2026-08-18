from threading import Thread, Event
from game_server.game.model import Deck, Game, Hand
from game_server.app import socketio
from game_server.app import central_client

BET_WINDOW_SECONDS = 35
ACTION_WINDOW_SECONDS = 60

class GameLoop(Thread):
    def __init__(self, table):
        super().__init__()
        self.table = table
        self.running = True
        self.bets_done_event = Event()
        self.actions_done_event = Event()
        self.room_id = f"table-{self.table.id}"

    def run(self):
        while self.table.is_ready_to_start():
            if not self._play_round():
                return
        self.running = False

    def _play_round(self):
        """Play one full round. Returns False when the round was cancelled
        because nobody bet, which ends the loop."""
        self.bets_done_event.clear()
        self.actions_done_event.clear()

        table_id = self.table.id
        socketio.emit('game_starting', {'table': table_id}, to=self.room_id)
        deck = Deck()
        game = Game(self.table.users, deck)
        self.table.game = game

        # Fase 0: richiedi puntate
        socketio.emit('place_bets', {'table': table_id}, to=self.room_id)
        self.bets_done_event.wait(timeout=BET_WINDOW_SECONDS)
        for user in self.table.users:
            if not game.bets.get(user):
                # Nessuna puntata -> escludi
                game.remove_active_user(user)

        if not game.active_users:
            socketio.emit('no_players_bet', {'table': table_id}, to=self.room_id)
            self._end_round()
            return False

        # Fase 1: distribuzione iniziale
        for user in game.active_users:
            user.add_card(deck.draw_card())
            user.add_card(deck.draw_card())

        # Notifica stato iniziale
        socketio.emit('initial_cards', {
            'table': table_id,
            'hands': {
                u.username: [str(c) for c in u.hand]
                for u in self.table.users
            }
        }, to=self.room_id)

        # Finestra di azione per i giocatori dal frontend
        self.actions_done_event.wait(ACTION_WINDOW_SECONDS)

        # Chi non ha agito -> stand automatico
        for user in game.active_users[:]:  # copia per evitare modifiche su lista iterata
            game.player_stand(user)
            socketio.emit('player_auto_stand', {
                'user': user.username,
                'table': table_id
            }, to=self.room_id)

        # Fase 5: turno dealer
        while Hand.get_hand_value(game.dealer_hand) < Game.DEALER_STAND_VALUE:
            game.add_dealer_card(deck.draw_card())

        socketio.emit('dealer_done', {
            'cards': [str(c) for c in game.dealer_hand]
        }, to=self.room_id)

        # Fase 6: risultati e bilanci
        results = game.determine_result()
        socketio.emit('round_results', {
            'results': [r.to_dict() for r in results]
        }, to=self.room_id)

        central_client.send_results(results)
        self._end_round()
        return True

    def _end_round(self):
        """Smonta il round: gli observer diventano giocatori e il tavolo torna
        libero per il round successivo."""
        self.table.clear_game()
