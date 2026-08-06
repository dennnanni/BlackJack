"""Socket.IO gameplay events.

Identity comes from the Flask session that POST /join populated after
verifying the signed join token: the client never supplies its own username
or balance.
"""
from flask import session
from flask_socketio import emit, join_room

from game_server.game.model import Hand, TableManager, User
from game_server.loop import GameLoop

table_manager = TableManager()
user_map = {}
table_game_map = {}


def seated_players():
    """Usernames currently seated on this server (reported to central: it is
    both the load figure and the renewal of these players' seat leases)."""
    return list(user_map)


def _room(table):
    return f"table-{table.id}"


def register_event_handlers(socketio):

    def _session_user():
        username = session.get('username')
        if username is None:
            emit('error', {'message': 'Join through the central server first'})
            return None
        return username

    @socketio.on('join')
    def handle_join():
        username = _session_user()
        if username is None:
            return

        if table_manager.has_user(username):
            # Reconnect (e.g. page refresh): rejoin the same table
            table = table_manager.get_user_table(username)
            join_room(_room(table))
            emit('joined', {'table_id': table.id,
                            'is_player': not table.is_game_active()})
        else:
            user = User(username, session['balance'])
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
                emit('joined', {'table_id': table_id, 'is_player': True}, to=_room(table))
            else:
                emit('joined', {'table_id': table.id, 'is_player': False}, to=_room(table))

        game = table.game
        if game:
            # Bring just this (re)joining client up to date with the board;
            # don't disturb the other players mid-turn.
            emit('initial_cards', {
                'table': table.id,
                'hands': {
                    u.username: [str(c) for c in u.hand]
                    for u in game.get_users()
                },
                'dealer_cards': [str(c) for c in game.dealer_hand]
            })

    @socketio.on('bet')
    def handle_bet(data):
        username = _session_user()
        if username is None:
            return

        user = user_map.get(username)
        table = table_manager.get_user_table(username)
        if not user or not table:
            emit('error', {'message': 'User not at any table'})
            return

        game = table.game
        if not game:
            emit('error', {'message': 'No active game'})
            return

        try:
            all_bet = game.place_bet(user, float(data['amount']))
        except (KeyError, TypeError, ValueError) as e:
            emit('error', {'message': str(e)})
            return

        emit('bet_confirmed', {'user': username, 'amount': game.bets.get(user)}, to=_room(table))
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
            emit('error', {'message': 'User not at any table'})
            return
        game = table.game
        if not game:
            emit('error', {'message': 'No active game'})
            return

        # Turn order is enforced here: only the player the loop is currently
        # waiting on may act. Anyone else is politely told to wait their turn.
        game_loop = table_game_map.get(table.id)
        current = game_loop.current_player if game_loop else None
        if current is None or current.username != username:
            emit('error', {'message': "It's not your turn yet"})
            return
        user = current

        action = data.get('action')  # 'hit', 'stand', 'double'
        room_id = _room(table)

        if action == 'hit':
            card = game.deck.draw_card()
            user.add_card(card)
            emit('card_drawn', {'user': username, 'card': str(card)}, to=room_id)
            if Hand.is_busted(user.hand):
                game.remove_active_user(user)
                emit('player_busted', {'user': username}, to=room_id)
        elif action == 'stand':
            game.player_stand(user)
            emit('user_stood', {'user': username}, to=room_id)
        elif action == 'double':
            try:
                card = game.player_double_down(user)
                emit('user_doubled', {'user': username, 'card': str(card)}, to=room_id)
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
            return
        table_manager.remove_user(user)
        del user_map[username]
