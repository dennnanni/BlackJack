import time

from flask import session
from flask_socketio import emit, join_room

from game_server.app import outbox
from game_server.game.model import Hand, TableManager, User
from game_server.loop import GameLoop

table_manager = TableManager()
user_map = {}
table_game_map = {}

# Players who asked to skip rounds
sitting_out = set()

# Ids of buy-ins that already seated a player.
seated_buy_ins = set()

# Players who went away keep their seat until the end of the
# round and are unseated then if they never came back
absent = {}


def seated_players():
    """Usernames seated here. Central reads it as our load and as the renewal
    of these players' seat leases."""
    return list(user_map)


def _room(table):
    return f"table-{table.id}"


def can_take_seat(buy_in_id, join_exp):
    """Whether a session may still sit down: its buy-in has not seated anyone
    yet and the join token that brought it has not expired."""
    return (buy_in_id is not None and buy_in_id not in seated_buy_ins
            and time.time() <= join_exp)


def unseat(username, close_buy_in=True):
    """Remove a player from their table and have central close their buy-in,
    handing what is left of it back to their balance."""
    user = user_map.pop(username, None)
    if user is None:
        return
    table_manager.remove_user(user)
    absent.pop(username, None)
    sitting_out.discard(username)
    if close_buy_in and user.buy_in_id:
        outbox.enqueue_leave(user.buy_in_id)


def leave_table(username):
    """A player pressed "Leave table"."""

    from game_server.app import socketio   # circular at import time

    user = user_map.get(username)
    if user is None:
        return
    table = table_manager.get_user_table(username)
    game = table.game if table else None
    # With a stake in play the buy-in closes after the round's result,
    # or central would refund the stake before charging the loss.
    stake_in_play = game is not None and user in game.bets
    if game and user in game.get_users():
        game.forfeit(user)
        game_loop = table_game_map.get(table.id)
        if game_loop and game_loop.current_player is user:
            game_loop.turn_done_event.set()   # don't hold the table for them
        socketio.emit('player_left', {'user': username}, to=_room(table))
    unseat(username, close_buy_in=not stake_in_play)


def close_forfeited_buy_ins(game):
    """Called by the loop when a round is over, after its results are in the
    outbox: close the buy-ins leave_table kept open for a stake in play."""
    for user in game.forfeited:
        if user in game.bets and user.buy_in_id:
            outbox.enqueue_leave(user.buy_in_id)


def reap_absent(table):
    """Called by the loop between rounds: unseat the players of this table
    whose socket never came back."""
    for username in [u for u in list(absent) if table_manager.get_user_table(u) is table]:
        unseat(username)


def register_event_handlers(socketio):

    def _session_user():
        username = session.get('username')
        if username is None:
            emit('error', {'message': 'Join through the central server first'})
            return None
        return username

    def _resume(user, table):
        """Puts a reconnecting client back where it was instead of dealing
        it a second seat at another table."""
        room_id = _room(table)
        join_room(room_id)

        game = table.game
        game_loop = table_game_map.get(table.id)
        payload = {
            'table_id': table.id,
            'balance': user.balance,
            'sitting_out': user.username in sitting_out,
            'hand': [str(c) for c in user.hand],
            'in_round': game is not None,
        }
        if game:
            payload['dealer_cards'] = [str(c) for c in game.dealer_hand]
            payload['hands'] = {
                u.username: [str(c) for c in u.hand] for u in table.users
            }
            payload['betting_open'] = bool(game_loop and game_loop.betting_open)
            payload['bet_seconds_left'] = game_loop.bet_seconds_left() if game_loop else 0
            payload['your_turn'] = bool(game_loop and game_loop.current_player is user)
            payload['bet_amount'] = game.bets.get(user)
        emit('resumed', payload)

    @socketio.on("join")
    def handle_join():
        username = _session_user()
        if username is None:
            return
        absent.pop(username, None)

        existing_user = user_map.get(username)
        existing_table = table_manager.get_user_table(username) if existing_user else None
        if existing_user and existing_table:
            _resume(existing_user, existing_table)
            return

        # A new seat needs a buy-in that has not seated anyone yet: once its
        # player has left, this session must go back to central for another.
        buy_in_id = session.get('buy_in_id')
        if not can_take_seat(buy_in_id, session.get('join_exp', 0)):
            emit('seat_closed', {'message': 'Your seat at this table is over: '
                                            'back to the central server to play again'})
            return
        seated_buy_ins.add(buy_in_id)

        user = User(username, session['balance'], buy_in_id)
        user_map[username] = user
        table = table_manager.assign_user_to_table(user)

        join_room(_room(table))

        if table.is_ready_to_start():
            table_id = table.id
            existing_loop = table_game_map.get(table_id)
            if not existing_loop or not existing_loop.running:
                game_loop = GameLoop(table)
                table_game_map[table_id] = game_loop
                game_loop.start()
            emit("joined", {"table_id": table.id, "is_player": True})
        else:
            emit("joined", {"table_id": table.id, "is_player": False})

        if table.game:
            emit("initial_cards", {
                "table": table.id,
                "hands": {
                    u.username: [str(c) for c in u.hand]
                    for u in table.users
                },
                'dealer_cards': [str(c) for c in table.game.dealer_hand]
            })

    @socketio.on('sit_out')
    def handle_sit_out(data):
        """Toggle sitting out. The flag can be set at any time but only takes
        effect at a round boundary: nobody is pulled out of a hand they have
        already been dealt, and nobody is dealt into one already running."""
        username = _session_user()
        if username is None:
            return
        user = user_map.get(username)
        table = table_manager.get_user_table(username)
        if not user or not table:
            emit('error', {'message': 'User not at any table'})
            return

        out = bool(data.get('sitting_out'))
        sitting_out.add(username) if out else sitting_out.discard(username)

        game, game_loop = table.game, table_game_map.get(table.id)
        # Only the betting window is early enough to change the round that is
        # already on the table; after that the change waits for the next one.
        applies_now = not game or (game_loop is not None and game_loop.betting_open)
        emit('seat_state', {'sitting_out': out, 'applies_now': applies_now})
        if not applies_now or not game:
            return

        if out:
            game.bets.pop(user, None)
            game.remove_active_user(user)
        else:
            game.restore_active_user(user)
        # The table no longer has to wait for a player who is not playing.
        if game_loop and game.all_players_have_bet():
            game_loop.bets_done_event.set()

    @socketio.on("bet")
    def handle_bet(data):
        username = _session_user()
        if username is None:
            return

        user = user_map.get(username)
        table = table_manager.get_user_table(username)
        if not user or not table:
            emit("error", {"message": "User not at any table"})
            return
        game = table.game
        if not game:
            emit("error", {"message": "No active game"})
            return
        room_id = _room(table)

        # A player who bet stays active through the turns, so place_bet alone
        # would let them change their stake after seeing their cards.
        game_loop = table_game_map.get(table.id)
        if not game_loop or not game_loop.betting_open:
            emit("error", {"message": "Betting is closed"})
            return

        try:
            all_bet = game.place_bet(user, float(data["amount"]))
        except (KeyError, TypeError, ValueError) as e:
            emit("error", {"message": str(e)})
            return

        emit("bet_confirmed", {"user": username, "amount": game.bets.get(user)}, to=room_id)
        if all_bet:
            game_loop.bets_done_event.set()
            
    @socketio.on('player_action')
    def handle_player_action(data):
        username = _session_user()
        if username is None:
            return

        table = table_manager.get_user_table(username)
        if not table:
            emit("error", {"message": "User not at any table"})
            return
        game = table.game
        if not game:
            emit("error", {"message": "No active game"})
            return
        room_id = _room(table)

        # Turn order is enforced here: only the player the loop is currently
        # waiting on may act.
        game_loop = table_game_map.get(table.id)
        current = game_loop.current_player if game_loop else None
        if current is None or current.username != username:
            emit("error", {"message": "It's not your turn yet"})
            return
        user = current

        action = data['action']  # 'hit', 'stand', 'double'

        if action == 'hit':
            card = game.deck.draw_card()
            user.add_card(card)
            emit("card_drawn", {"user": username, "card": str(card)}, to=room_id)
            if Hand.is_busted(user.hand):
                game.remove_active_user(user)
                emit('player_busted', {'user': username}, to=room_id)
        elif action == 'stand':
            game.player_stand(user)
            emit("user_stood", {"user": username}, to=room_id)
        elif action == 'double':
            try:
                card = game.player_double_down(user)
                emit("user_doubled", {"user": username, "card": str(card)}, to=room_id)
                if Hand.is_busted(user.hand):
                    emit('player_busted', {'user': username}, to=room_id)
            except (ValueError, KeyError) as e:
                emit('error', {'user': username, 'message': str(e)})
                return
        else:
            emit('error', {'message': f'Unknown action: {action}'})
            return

        # The turn ends the moment the player is no longer active (they stood,
        # doubled or busted); a plain hit leaves them active to act again.
        if user not in game.active_users:
            game_loop.turn_done_event.set()

    @socketio.on('disconnect')
    def handle_disconnect():
        username = session.get('username')
        if username is None or username not in user_map:
            return
        # Never unseated on the spot, not even between rounds: unseating closes
        # the buy-in, and a page reload must not cost a player that. The loop
        # stops waiting for them after ABSENT_GRACE_SECONDS and unseats them
        # at the end of the round unless they reconnect first.
        absent.setdefault(username, time.monotonic())