from socket import SocketIO
from client.controller.client_controller import add_user

def register_event_handlers(socketio):
    socketio.on_event('add_user', add_user)