from flask_socketio import emit, on
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
        table, is_player = table_manager.assign_user_to_table(user)
        
        emit("joined", {"table_id": table.get_table_id(), "is_player": is_player})
        if table.is_ready_to_start():
            table_game_map.pop(table.get_table_id, GameLoop(table).start())

    @socketio.on("bet")
    def handle_bet(data):
        username = data["username"]
        amount = float(data["amount"])
        user = user_map[username]
        table = table_manager.get_user_table(username)
        if not table or not table.game:
            emit("error", {"message": "No active game"})
            return

        try:
            if table.game.place_bet(user, amount):
                table_game_map.get(table.get_table_id).bets_done_event.set()
            
            emit("bet_confirmed", {"user": username, "amount": amount}, broadcast=True)
        except Exception as e:
            emit("error", {"message": str(e)})
            
    @socketio.on('player_action')
    def handle_player_action(data):
        username = data['username']
        user = user_map[username]
        action = data['action']  # 'hit', 'stand', 'double'
        
        table = table_manager.get_user_table(username)
        if not table or not table.is_game_active():
            return

        game = table.get_game()
        user = next((u for u in game.get_users() if u.get_username() == username), None)
        if not user:
            return

        if action == 'hit':
            user.add_card(game.get_deck().draw_card())  # accedi al deck privato
            if Hand.is_busted(user.get_hand()):
                game.remove_active_user(user)
                socketio.emit('player_busted', {'user': username})
        elif action == 'stand':
            game.player_stand(user)
        elif action == 'double':
            try:
                game.player_double_down(user)
            except ValueError as e:
                socketio.emit('error', {'user': username, 'message': str(e)})
                
        if table.get_game().all_players_done():
            table_game_map.get(table.get_table_id).actions_done_event.set()

        socketio.emit('player_action_done', {
            'user': username,
            'hand': [str(c) for c in user.get_hand()]
        })

