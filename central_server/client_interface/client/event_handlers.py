from client.controller.client_controller import get_user_info, get_game_server

def register_event_handlers(socketio):
    socketio.on_event('get_user_info', get_user_info)
    socketio.on_event('get_game_server', get_game_server)