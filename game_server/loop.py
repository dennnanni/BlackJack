from threading import Thread, Event
from game_server.game.model import Deck, Game, Hand
from game_server.app import socketio
from game_server.app import central_client

BET_WINDOW_SECONDS = 35
TURN_WINDOW_SECONDS = 30

# Pacing delays (seconds) so players can actually watch the round unfold instead
# of the dealer and results flashing past.
PRE_DEALER_DELAY = 1.5      # a beat after the last player, before the dealer acts
DEALER_DRAW_DELAY = 1.2     # between each dealer card, so the hand builds up visibly
POST_DEALER_DELAY = 2.0     # let the finished dealer hand sink in
ROUND_RESULT_DELAY = 7      # show the outcome and final hands before the table resets

IDLE_ROUND_SECONDS = 3

class GameLoop(Thread):
    def __init__(self, table):
        super().__init__()
        self.table = table
        self.running = True
        self.bets_done_event = Event()
        # Impostato dall'event handler quando il giocatore di turno ha finito
        # (stand, double o bust). current_player e' l'utente che il loop sta
        # aspettando: l'handler lo legge per far rispettare il turno.
        self.turn_done_event = Event()
        self.current_player = None
        # Fase del round, per i client che si (ri)collegano a meta' partita.
        self.betting_open = False
        self.room_id = f"table-{self.table.id}"

    def run(self):
        # Keep offering rounds for as long as anyone is seated. Each iteration
        # is a full round; nothing here waits for a human to restart it.
        while self.table.is_ready_to_start():
            self._play_round()
        self.running = False

    def _play_round(self):
        self.bets_done_event.clear()

        table_id = self.table.id
        socketio.emit('game_starting', {'table': table_id}, to=self.room_id)
        deck = Deck()
        game = Game(self.table.users[:], deck)
        self.table.game = game

        # Chi si e' chiamato fuori non e' proprio in questo round, cosi' il
        # tavolo non lo aspetta.
        from game_server.events import sitting_out
        for user in self.table.users:
            if user.username in sitting_out:
                game.remove_active_user(user)

        if not game.active_users:
            # Nessuno sta giocando: resta in attesa invece di girare a vuoto.
            socketio.emit('table_idle', {'table': table_id}, to=self.room_id)
            socketio.sleep(IDLE_ROUND_SECONDS)
            self._end_round()
            return

        # Fase 0: richiedi puntate
        socketio.emit('place_bets', {'table': table_id}, to=self.room_id)
        self.betting_open = True
        self.bets_done_event.wait(timeout=BET_WINDOW_SECONDS)
        self.betting_open = False
        for user in self.table.users:
            if not game.bets.get(user):
                # Nessuna puntata -> escludi
                game.remove_active_user(user)

        if not game.bets:
            # Nessuna puntata: annulla e riapri subito una finestra di puntate
            # (ci pensa il while esterno). Nessun reload.
            socketio.emit('no_players_bet', {'table': table_id}, to=self.room_id)
            self._end_round()
            return

        # Fase 1: distribuzione iniziale. Due carte a chi ha puntato, poi la
        # carta scoperta del dealer: cosi' si decide contro qualcosa invece che
        # al buio. Niente carta coperta, il dealer pesca il resto nella fase 4.
        for user in game.active_users:
            user.clear_hand()
            user.add_card(deck.draw_card())
            user.add_card(deck.draw_card())
        game.add_dealer_card(deck.draw_card())

        # Notifica stato iniziale
        socketio.emit('initial_cards', {
            'table': table_id,
            'hands': {
                u.username: [str(c) for c in u.hand]
                for u in game.active_users
            },
            'dealer_cards': [str(c) for c in game.dealer_hand]
        }, to=self.room_id)

        # Fase 2: i turni, uno alla volta finche' il giocatore ha finito
        for user in list(game.active_users):
            self._run_turn(game, user)
        self.current_player = None

        # Fase 3: il dealer completa la mano partendo dalla carta scoperta,
        # rivelando una carta alla volta.
        socketio.sleep(PRE_DEALER_DELAY)
        socketio.emit('dealer_turn', {'table': table_id}, to=self.room_id)
        while Hand.get_hand_value(game.dealer_hand) < Game.DEALER_STAND_VALUE:
            card = deck.draw_card()
            game.add_dealer_card(card)
            socketio.emit('dealer_card', {
                'card': str(card),
                'cards': [str(c) for c in game.dealer_hand]
            }, to=self.room_id)
            socketio.sleep(DEALER_DRAW_DELAY)
        socketio.emit('dealer_done', {
            'cards': [str(c) for c in game.dealer_hand]
        }, to=self.room_id)
        socketio.sleep(POST_DEALER_DELAY)

        # Fase 4: risultati e bilanci
        results = game.determine_result()
        central_client.send_results(results)
        socketio.emit('round_results', {
            'results': [r.to_dict() for r in results],
            'next_round_in': ROUND_RESULT_DELAY
        }, to=self.room_id)

        # Fase 5: lascia il tempo di guardare l'esito e le mani finali, poi
        # smonta il round; il while esterno fa partire il prossimo.
        socketio.sleep(ROUND_RESULT_DELAY)
        self._end_round()

    def _end_round(self):
        """Smonta il round: gli observer diventano giocatori e il tavolo torna
        libero per il round successivo."""
        self.table.clear_game()

    def _run_turn(self, game, user):
        """Da' il tavolo a un giocatore finche' non sta, raddoppia, sballa o
        scade il tempo."""
        if user not in game.active_users:
            return
        username = user.username

        # Una mano che vale gia' 21 (blackjack compreso) non puo' migliorare:
        # stand automatico invece di aspettare un'azione che non arrivera'.
        if Hand.get_hand_value(user.hand) >= Hand.BLACKJACK:
            game.player_stand(user)
            socketio.emit('user_stood', {'user': username}, to=self.room_id)
            return

        self.current_player = user
        self.turn_done_event.clear()
        socketio.emit('turn_started', {'user': username, 'table': self.table.id},
                      to=self.room_id)

        # L'intero turno, per quanti hit voglia fare, condivide questa finestra.
        self.turn_done_event.wait(TURN_WINDOW_SECONDS)

        if user in game.active_users:
            game.player_stand(user)
            socketio.emit('player_auto_stand', {'user': username, 'table': self.table.id},
                          to=self.room_id)
