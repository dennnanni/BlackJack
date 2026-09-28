import time

from flask import session
from flask_socketio import emit, join_room

from game_server.game.model import Hand, User
from game_server.loop import GameLoop
from game_server.runtime import closing
from game_server.seats import (absent, can_take_seat, room, seated_buy_ins, sitting_out,
                               table_game_map, table_manager, user_map)


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
        room_id = room(table)
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
        if not can_take_seat(buy_in_id, session.get('join_exp', 0), session.get('boot_id')):
            if closing.is_set():
                message = 'This server is shutting down: back to the central server to play again'
            else:
                message = 'Your seat at this table is over: back to the central server to play again'
            emit('seat_refused', {'message': message})
            return
        seated_buy_ins.add(buy_in_id)

        user = User(username, session['balance'], buy_in_id)
        user_map[username] = user
        table = table_manager.assign_user_to_table(user)

        join_room(room(table))

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
        room_id = room(table)

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
        room_id = room(table)

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
        # The player is never removed from the table immediately, not even between rounds: unseating closes
        # the buy-in, and a page reload must not cost a player that. The loop
        # stops waiting for them after ABSENT_GRACE_SECONDS and unseats them
        # at the end of the round unless they reconnect first.
        absent.setdefault(username, time.monotonic())