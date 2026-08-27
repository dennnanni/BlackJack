from flask_socketio import emit, join_room
from flask_socketio import SocketIO
from game_server.game.model import User, TableManager, Hand
from game_server.loop import GameLoop
from game_server.app import central_client

table_manager = TableManager()
user_map = {}
table_game_map = {}

# Players who asked to skip rounds. Sitting out is not the same as not
# betting: the loop does not deal them in and, above all, does not wait on
# them, so the rest of the table starts as soon as *they* have bet instead of
# sitting through the whole betting window.
sitting_out = set()

def register_event_handlers(socketio):

    @socketio.on("join")
    def handle_join(data):
        username = data["username"]
        balance = data["balance"]
        user = User(username, balance)
        user_map[username] = user
        table = table_manager.assign_user_to_table(user)
        
        room_id = f"table-{table.id}"
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
            
        central_client.update_user_list(list(user_map.keys()))

    @socketio.on('sit_out')
    def handle_sit_out(data):
        """Toggle sitting out. The flag can be set at any time but only takes
        effect at a round boundary: nobody is pulled out of a hand they have
        already been dealt, and nobody is dealt into one already running."""
        username = data['username']
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
        username = data["username"]
        user = user_map[username]
        table = table_manager.get_user_table(username)

        if not table:
            emit("error", {"message": "User not at any table"})
            return
        room_id = f"table-{table.id}"
        game = table.game
        if not game:
            emit("error", {"message": "No active game"}, to=room_id)
            return

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
        username = data['username']
        table = table_manager.get_user_table(username)

        if not table:
            emit("error", {"message": "User not at any table"})
            return
        room_id = f"table-{table.id}"
        game = table.game
        if not game:
            emit("error", {"message": "No active game"}, to=room_id)
            return

        # Turn order is enforced here: only the player the loop is currently
        # waiting on may act. Anyone else is politely told to wait their turn.
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