from flask_socketio import emit, on, join_room
from src.model.game_structures import User, TableManager, Hand
from src.game_loop import GameLoop

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
        table, is_player = table_manager.assign_user_to_table(user)#voglio far diventare isPlayer true se può entrare nel server, false altrimenti
        
        room_id = f"table-{table.get_table_id()}"
        join_room(room_id)
        
        emit("joined", {"table_id": table.get_table_id(), "is_player": is_player}, to=room_id)
        if table.is_ready_to_start():
            table_id = table.get_table_id()
            existing_loop = table_game_map.get(table_id)
            if not existing_loop or not existing_loop.is_alive():    
                game_loop = GameLoop(table)
                table_game_map[table_id] = game_loop
                game_loop.start()
                
        if table.get_game():
            emit("initial_cards", {
                "table": table.get_table_id(),
                "hands": {
                    u.get_username(): [str(c) for c in u.get_hand()]
                    for u in table.get_users()
                },
                'cards': [str(c) for c in table.get_game().get_dealer_hand()]
            }, to=room_id)

    @socketio.on("bet")
    def handle_bet(data):
        username = data["username"]
        amount = float(data["amount"])
        user = user_map[username]
        table = table_manager.get_user_table(username)
        
        if not table:
            emit("error", {"message": "User not at any table"})
            return
        room_id = f"table-{table.get_table_id()}"
        if not table.get_game():
            emit("error", {"message": "No active game"}, to=room_id)
            return

        try:
            if table.get_game().place_bet(user, amount):
                game_loop = table_game_map.get(table.get_table_id())
                if game_loop:
                    game_loop.bets_done_event.set()

            if table.get_game().all_players_have_bet():
                game_loop.bets_done_event.set()
                emit("bet_confirmed", {"user": username, "amount": amount}, to=room_id)
        except Exception as e:
            emit("error", {"message": str(e)}, to=room_id)
            
    @socketio.on('player_action')
    def handle_player_action(data):
        username = data['username']
        user = user_map[username]
        action = data['action']  # 'hit', 'stand', 'double'
        table = table_manager.get_user_table(username)
        game = table.get_game()
        
        if not table:
            emit("error", {"message": "User not at any table"})
            return
        room_id = f"table-{table.get_table_id()}"
        if not table.is_game_active():
            emit("error", {"message": "No active game"}, to=room_id)
            return

        user = next((u for u in game.get_users() if u.get_username() == username), None)
        if not user:
            return

        if action == 'hit':
            card = game.get_deck().draw_card()
            user.add_card(card)
            emit("card_drawn", {"user": username, "card": str(card)}, to=room_id)
            if Hand.is_busted(user.get_hand()):
                game.remove_active_user(user)
                emit('player_busted', {'user': username}, to=room_id)
        elif action == 'stand':
            game.remove_active_user(user)
            emit("user_stood", {"user": username}, to=room_id)
        elif action == 'double':
            try:
                card = game.player_double_down(user)
                emit("user_doubled", {
                "user": username,
                "card": str(card)
                }, to=room_id)
            except ValueError as e:
                emit('error', {'user': username, 'message': str(e)}, to=room_id)
                
        if table.get_game().all_players_done():
            table_game_map.get(table.get_table_id()).actions_done_event.set()
            emit('player_action_done', to=room_id)