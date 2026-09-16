import time
from threading import Thread, Event
from uuid import uuid4
from game_server.game.model import Deck, Game, Hand
from game_server.app import outbox, socketio
from game_server.central_client import client

BET_WINDOW_SECONDS = 35
TURN_WINDOW_SECONDS = 30

# Pacing delays (seconds) so players can actually watch the round unfold instead
# of the dealer and results flashing past.
PRE_DEALER_DELAY = 1.5      # a beat after the last player, before the dealer acts
DEALER_DRAW_DELAY = 1.2     # between each dealer card, so the hand builds up visibly
POST_DEALER_DELAY = 2.0     # let the finished dealer hand sink in
ROUND_RESULT_DELAY = 7      # show the outcome and final hands before the table resets

LEASE_CHECK_SECONDS = 1    # how often does a freezer table check the lease
IDLE_ROUND_SECONDS = 3

# A player whose socket dropped is still waited for this long, so that a page
# reload does not cost them their bet or their turn; after it the table moves on.
ABSENT_GRACE_SECONDS = 5
WAIT_POLL_SECONDS = 0.5    # how often a waiting table checks who is still around

class GameLoop(Thread):
    def __init__(self, table):
        super().__init__()
        self.table = table
        self.running = True
        self.bets_done_event = Event()
        # Set by the event handler when the current player has finished their 
        # turn (stand, double, or bust). `current_player` is the user the loop
        # is waiting for; the handler reads it to enforce turn order.
        self.turn_done_event = Event()
        self.current_player = None
        # Fase del round, per i client che si collegano a meta' partita.
        self.betting_open = False
        self.bet_deadline = 0.0
        self.room_id = f"table-{self.table.id}"

    def bet_seconds_left(self):
        """Seconds remaining to place a bet, accounting for the 
            timer for clients connecting after the window has already opened."""
        if not self.betting_open:
            return 0
        return max(0.0, self.bet_deadline - time.monotonic())

    def run(self):
        # Keep offering rounds for as long as anyone is seated. Each iteration
        # is a full round; nothing here waits for a human to restart it, only
        # the lease can hold the next one back.
        while self.table.is_ready_to_start():
            self._await_lease()
            if not self.table.is_ready_to_start():
                break  # se ne sono andati tutti mentre il tavolo era congelato
            self._play_round()
        self.running = False

    def _await_lease(self):
        """Freezes new rounds until the lease expires. 

            Prevents player funds from being committed if the connection to the center is lost
            (as the center might reassign seats). The table pauses without ejecting anyone
            and resumes automatically once the connection is restored. Rounds already in progress
            are always completed normally and sent to the outbox."""
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

        # Anyone who has opted out isn't in this round, so the
        # table doesn't wait for them.
        from game_server.events import sitting_out
        for user in self.table.users:
            if user.username in sitting_out:
                game.remove_active_user(user)

        if not game.active_users:
            # No one is playing, waiting
            socketio.emit('table_idle', {'table': table_id}, to=self.room_id)
            socketio.sleep(IDLE_ROUND_SECONDS)
            self._end_round()
            return

        # Phase 0: Request bets.
        self.bet_deadline = time.monotonic() + BET_WINDOW_SECONDS
        self.betting_open = True
        socketio.emit('place_bets', {'table': table_id, 'seconds': BET_WINDOW_SECONDS},
                      to=self.room_id)
        self._wait_for_players(self.bets_done_event, BET_WINDOW_SECONDS,
                               lambda: [u for u in game.active_users if u not in game.bets])
        self.betting_open = False
        for user in self.table.users:
            if not game.bets.get(user):
                # No bet placed -> exclude
                game.remove_active_user(user)

        if not game.bets:
            # No bets placed: cancel and reopen bet window immediately
            socketio.emit('no_players_bet', {'table': table_id}, to=self.room_id)
            self._end_round()
            return

        # lease check
        if not client.lease_valid():
            self._end_round()
            return

        # Phase 1: Initial deal. Two cards to each player who placed a bet, then the
        # dealer's face-up card.
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

        # Phase 2: Turns, one at a time until the player is done
        for user in list(game.active_users):
            self._run_turn(game, user)
        self.current_player = None

        # Phase 3: The dealer completes the hand starting from the face-up card,
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

        # Phase 4: results and balances. First write to the outbox
        # then notify the table
        results = game.determine_result()
        outbox.enqueue(str(uuid4()), results)
        socketio.emit('round_results', {
            'results': [r.to_dict() for r in results],
            'next_round_in': ROUND_RESULT_DELAY
        }, to=self.room_id)

        # Phase 5: leave time to view the outcome and final hands, then
        # end the round
        socketio.sleep(ROUND_RESULT_DELAY)
        self._end_round()

    def _end_round(self):
        """End the round and start the next one: observers become players,
        and anyone who hasn't shown up gives up their spot."""
        from game_server.events import reap_absent  # circolare a import time
        self.table.clear_game()
        reap_absent(self.table)

    def _wait_for_players(self, event, timeout, waiting_on):
        """The handlers set the event for the common cases; this covers the
        ones where nobody is left to set it."""
        from game_server.events import absent
        deadline = time.monotonic() + timeout
        while not event.is_set():
            now = time.monotonic()
            if now >= deadline:
                return
            if all(now - absent.get(u.username, now) > ABSENT_GRACE_SECONDS
                   for u in waiting_on()):
                return
            event.wait(min(WAIT_POLL_SECONDS, deadline - now))

    def _run_turn(self, game, user):
        """Give the table to a player until they stand, double down, or
        the time runs out."""
        if user not in game.active_users:
            return
        username = user.username

        # blackjack hand leads to automatic stand, no need to wait for the player to act
        if Hand.get_hand_value(user.hand) >= Hand.BLACKJACK:
            game.player_stand(user)
            socketio.emit('user_stood', {'user': username}, to=self.room_id)
            return

        self.current_player = user
        self.turn_done_event.clear()
        socketio.emit('turn_started', {'user': username, 'table': self.table.id},
                      to=self.room_id)

        # The entire turn, for as many hits they want to make, sharing this window.
        self._wait_for_players(self.turn_done_event, TURN_WINDOW_SECONDS,
                               lambda: [user] if user in game.active_users else [])

        if user in game.active_users:
            game.player_stand(user)
            socketio.emit('player_auto_stand', {'user': username, 'table': self.table.id},
                          to=self.room_id)
