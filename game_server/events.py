from flask import session
from flask_socketio import emit, join_room

from game_server.game.model import Hand, TableManager, User
from game_server.loop import GameLoop

table_manager = TableManager()
user_map = {}
table_game_map = {}

# Players who asked to skip rounds
sitting_out = set()

# Balance of a player who left the table, so that closing and reopening the
# page does not rewind them to the snapshot their (older) join token carried.
last_balance = {}

# Players whose socket went away mid-round. They keep their seat until the
# round they are in is over. They are unseated afterwards if they never came
# back.
absent = set()


def _room(table):
    return f"table-{table.id}"


def unseat(username):
    """Remove a player from their table, remembering the balance they leave
    with."""
    user = user_map.pop(username, None)
    if user is None:
        return
    table_manager.remove_user(user)
    last_balance[username] = user.balance
    absent.discard(username)
    sitting_out.discard(username)


def leave_table(username):
    """A player pressed "Leave table"."""
    
    from game_server.app import socketio   # circular at import time

    user = user_map.get(username)
    if user is None:
        return
    table = table_manager.get_user_table(username)
    game = table.game if table else None
    if game and user in game.get_users():
        game.forfeit(user)
        game_loop = table_game_map.get(table.id)
        if game_loop and game_loop.current_player is user:
            game_loop.turn_done_event.set()   # don't hold the table for them
        socketio.emit('player_left', {'user': username}, to=_room(table))
    unseat(username)


def reap_absent(table):
    """Called by the loop between rounds: unseat the players of this table
    whose socket never came back."""
    for username in [u for u in absent if table_manager.get_user_table(u) is table]:
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
            payload['your_turn'] = bool(game_loop and game_loop.current_player is user)
            payload['bet_amount'] = game.bets.get(user)
        emit('resumed', payload)

    @socketio.on("join")
    def handle_join():
        username = _session_user()
        if username is None:
            return
        absent.discard(username)   # they are back (or never really left)

        existing_user = user_map.get(username)
        existing_table = table_manager.get_user_table(username) if existing_user else None
        if existing_user and existing_table:
            _resume(existing_user, existing_table)
            return

        # A player who left and came back keeps the balance they walked away
        # with; the session snapshot is only right the first time.
        user = User(username, last_balance.pop(username, session['balance']))
        user_map[username] = user
        table = table_manager.assign_user_to_table(user)

        room_id = _room(table)
        join_room(room_id)

        if table.is_ready_to_start():
            table_id = table.id
            existing_loop = table_game_map.get(table_id)
            if not existing_loop or not existing_loop.running:    
                game_loop = GameLoop(table)
                table_game_map[table_id] = game_loop
                game_loop.start()
            emit("joined", {"table_id": table.id, "is_player": True}, to=room_id)
        else:
            emit("joined", {"table_id": table.id, "is_player": False}, to=room_id)
                
        if table.game:
            emit("initial_cards", {
                "table": table.id,
                "hands": {
                    u.username: [str(c) for c in u.hand]
                    for u in table.users
                },
                'dealer_cards': [str(c) for c in table.game.dealer_hand]
            }, to=room_id)

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

        try:
            all_bet = game.place_bet(user, float(data["amount"]))
        except (KeyError, TypeError, ValueError) as e:
            emit("error", {"message": str(e)})
            return

        emit("bet_confirmed", {"user": username, "amount": game.bets.get(user)}, to=room_id)
        if all_bet:
            game_loop = table_game_map.get(table.id)
            if game_loop:
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
        user = user_map[username]
        table = table_manager.get_user_table(username)
        if table and table.is_game_active() and user in table.game.get_users():
            # Mid-round: leave the user in place; the round finishes for them
            # via auto-stand and their result is still reported to central.
            # The loop unseats them after the round unless they reconnect
            absent.add(username)
            return
        unseat(username)