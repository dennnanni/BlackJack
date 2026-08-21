from flask_socketio import emit, join_room
from flask_socketio import SocketIO
from game_server.game.model import User, TableManager, Hand
from game_server.loop import GameLoop
from game_server.app import central_client

table_manager = TableManager()
user_map = {}
table_game_map = {}

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
        user = user_map[username]
        action = data['action']  # 'hit', 'stand', 'double'
        table = table_manager.get_user_table(username)
        game = table.game
        
        if not table:
            emit("error", {"message": "User not at any table"})
            return
        room_id = f"table-{table.id}"
        if not table.is_game_active():
            emit("error", {"message": "No active game"}, to=room_id)
            return

        user = next((u for u in game.active_users if u.username == username), None)
        if not user:
            return

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
                emit('error', {'user': username, 'message': str(e)}, to=room_id)
                
        if table.game.all_players_done():
            table_game_map.get(table.id).actions_done_event.set()
            emit('player_action_done', to=room_id)