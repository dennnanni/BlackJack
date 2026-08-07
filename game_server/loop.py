"""Round state machine: one GameLoop thread drives the rounds of one table.

A round is: collect opt-in bets -> deal -> let each player act **in turn** ->
dealer completes -> pay out -> tear down. The while-loop then starts the next
round on its own, so a finished (or empty) round never needs a page reload.
"""
from threading import Event, Thread
from uuid import uuid4

from game_server.app import outbox, socketio
from game_server.central_client import client
from game_server.game.model import Deck, Game, Hand

BET_WINDOW_SECONDS = 35
TURN_WINDOW_SECONDS = 30

# Pacing delays (seconds) so players can actually watch the round unfold instead
# of the dealer and results flashing past.
PRE_DEALER_DELAY = 1.5      # a beat after the last player, before the dealer acts
DEALER_DRAW_DELAY = 1.2     # between each dealer card, so the hand builds up visibly
POST_DEALER_DELAY = 2.0     # let the finished dealer hand sink in
ROUND_RESULT_DELAY = 7     # show the outcome and final hands before the table resets

LEASE_CHECK_SECONDS = 1    # how often a frozen table re-checks the lease
IDLE_ROUND_SECONDS = 3     # pause when every player at the table is sitting out


class GameLoop(Thread):
    def __init__(self, table):
        super().__init__(daemon=True)
        self.table = table
        self.running = True
        self.bets_done_event = Event()
        # Set by the event handler when the player whose turn it is finishes
        # (stands, doubles or busts). current_player is the User the loop is
        # currently waiting on; the handler reads it to enforce turn order.
        self.turn_done_event = Event()
        self.current_player = None
        # Which phase the round is in, for clients that (re)join mid-round and
        # have to be told what they missed.
        self.betting_open = False
        self.room_id = f"table-{table.id}"

    def run(self):
        # Keep offering rounds for as long as anyone is seated. Each iteration
        # is a full round; nothing here waits for a human to restart it — only
        # the lease can hold the next one back.
        while self.table.is_ready_to_start():
            self._await_lease()
            if not self.table.is_ready_to_start():
                break  # everyone left while the table was frozen
            self._play_round()
        self.running = False

    def _await_lease(self):
        """Hold the *next* round back while this server's lease has expired.

        Betting stakes money that only central can settle, and central will
        hand a silent server's players to someone else. So when central has
        been unreachable for longer than LEASE_TIMEOUT this server stops
        starting rounds: the table freezes, nobody is kicked, and play resumes
        by itself when the lease is renewed. A round already in progress is
        never aborted — it is dealt, settled and queued in the outbox as usual.
        """
        if client.lease_valid():
            return
        socketio.emit('lease_expired', {'table': self.table.id}, to=self.room_id)
        while not client.lease_valid() and self.table.is_ready_to_start():
            socketio.sleep(LEASE_CHECK_SECONDS)
        if client.lease_valid():
            socketio.emit('lease_restored', {'table': self.table.id}, to=self.room_id)

    def _play_round(self):
        self.bets_done_event.clear()
        table_id = self.table.id
        socketio.emit('game_starting', {'table': table_id}, to=self.room_id)

        deck = Deck()
        game = Game(self.table.users[:], deck)
        self.table.game = game

        # Players who asked to sit out are not in this round at all, so the
        # table never waits on them.
        from game_server.events import sitting_out  # circular at import time
        for user in self.table.users:
            if user.username in sitting_out:
                game.remove_active_user(user)

        if not game.active_users:
            # Nobody is playing: idle instead of spinning through empty rounds.
            socketio.emit('table_idle', {'table': table_id}, to=self.room_id)
            socketio.sleep(IDLE_ROUND_SECONDS)
            self._end_round()
            return

        # 1. Betting: players opt in by placing a bet within the window. Whoever
        #    does not bet simply sits the round out and stakes nothing.
        socketio.emit('place_bets', {'table': table_id}, to=self.room_id)
        self.betting_open = True
        self.bets_done_event.wait(timeout=BET_WINDOW_SECONDS)
        self.betting_open = False
        for user in self.table.users:
            if not game.bets.get(user):
                game.remove_active_user(user)

        if not game.bets:
            # Nobody opted in: cancel and immediately offer a fresh betting
            # round (the outer loop restarts us). No reload needed.
            socketio.emit('no_players_bet', {'table': table_id}, to=self.room_id)
            self._end_round()
            return

        # 2. Initial deal: two cards to every player who bet.
        for user in game.active_users:
            user.clear_hand()
            user.add_card(deck.draw_card())
            user.add_card(deck.draw_card())
        socketio.emit('initial_cards', {
            'table': table_id,
            'hands': {u.username: [str(c) for c in u.hand]
                      for u in game.active_users}
        }, to=self.room_id)

        # 3. Player turns: strictly one player at a time until they are done.
        for user in list(game.active_users):
            self._run_turn(game, user)
        self.current_player = None

        # 4. Dealer completes their hand (draw to 17), revealed one card at a
        #    time so players can watch it build up.
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

        # 5. Results: persist to the outbox *first* (so a crash or a partition
        #    towards central cannot lose the finished round), then notify the
        #    room. The sender thread delivers the deltas to central.
        results = game.determine_result()
        outbox.enqueue(str(uuid4()), results)
        socketio.emit('round_results', {
            'results': [r.to_dict() for r in results],
            'next_round_in': ROUND_RESULT_DELAY
        }, to=self.room_id)

        # 6. Give players time to take in the outcome and the final hands, then
        #    tear the round down; the while-loop starts the next one.
        socketio.sleep(ROUND_RESULT_DELAY)
        self._end_round()

    def _end_round(self):
        """Tear the round down and let the next one start: observers become
        players, and players whose socket never came back give up their seat
        (between rounds is the only moment where dropping them costs nobody
        anything)."""
        from game_server.events import reap_absent  # circular at import time
        self.table.clear_game()
        reap_absent(self.table)

    def _run_turn(self, game, user):
        """Give one player the table until they stand, double, bust or time out."""
        if user not in game.active_users:
            return
        username = user.username

        # A hand already worth 21 (including a natural blackjack) cannot improve:
        # stand automatically instead of waiting for input.
        if Hand.get_hand_value(user.hand) >= Hand.BLACKJACK:
            game.player_stand(user)
            socketio.emit('user_stood', {'user': username}, to=self.room_id)
            return

        self.current_player = user
        self.turn_done_event.clear()
        socketio.emit('turn_started', {'user': username, 'table': self.table.id},
                      to=self.room_id)

        # Wait for the player to finish acting (event set by the handler) or run
        # out of time; the whole turn — however many hits — shares this window.
        self.turn_done_event.wait(TURN_WINDOW_SECONDS)

        if user in game.active_users:
            game.player_stand(user)
            socketio.emit('player_auto_stand', {'user': username, 'table': self.table.id},
                          to=self.room_id)
