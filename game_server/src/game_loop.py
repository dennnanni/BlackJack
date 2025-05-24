import time
from threading import Thread, Event
from src.model.game_structures import Deck, Game, Hand, User
from src import socketio
from src import central_client

class GameLoop(Thread):
    def __init__(self, table):
        super().__init__()
        self.table = table
        self.running = True
        self.bets_done_event = Event()
        self.actions_done_event = Event()
        self.room_id = f"table-{self.table.get_table_id()}"

    def run(self):
        while self.table.is_ready_to_start():
            socketio.emit('game_starting', {'table': self.table.get_table_id()}, to=self.room_id)
            deck = Deck()
            game = Game(self.table.get_users(), deck)
            self.table.set_game(game)
            
            # Fase 0: richiedi puntate
            socketio.emit('place_bets', {'table': self.table.get_table_id()}, to=self.room_id)
            self.bets_done_event.wait(timeout=35)
            for user in self.table.get_users():
                if not game.get_userbet(user):
                    # Nessuna puntata -> escludi
                    game.remove_active_user(user)
                    
            if not game.get_active_users():
                socketio.emit('no_players_bet', {'table': self.table.get_table_id()}, to=self.room_id)
                self.table.clear_game()
                return
                    
            # Fase 1: distribuzione iniziale
            for user in game.get_active_users():
                user.add_card(deck.draw_card())
                user.add_card(deck.draw_card())

            # Notifica stato iniziale
            socketio.emit('initial_cards', {
                'table': self.table.get_table_id(),
                'hands': {
                    u.get_username(): [str(c) for c in u.get_hand()]
                    for u in self.table.get_users()
                }
            }, to=self.room_id)

            # Dai 15 secondi ai giocatori per agire dal frontend
            self.actions_done_event.wait(60)

            # Chi non ha agito -> stand automatico
            for user in game.get_active_users()[:]:  # copia per evitare modifiche su lista iterata
                game.player_stand(user)
                socketio.emit('player_auto_stand', {
                    'user': user.get_username(),
                    'table': self.table.get_table_id()
                }, to=self.room_id)


            # Fase 5: turno dealer
            while Hand.get_hand_value(game.get_dealer_hand()) < Game.DEALER_STAND_VALUE:
                game.add_dealer_card(deck.draw_card())

            socketio.emit('dealer_done', {
                'cards': [str(c) for c in game.get_dealer_hand()]
            }, to=self.room_id)

            # Fase 6: risultati e bilanci
            results = game.determine_result()
            socketio.emit('round_results', {
                'results': [vars(r) for r in results]
            }, to=self.room_id)
            
            central_client.send_results(results)
            self.table.clear_game()
            self.bets_done_event.clear()
            self.actions_done_event.clear()
        
        self.running = False

