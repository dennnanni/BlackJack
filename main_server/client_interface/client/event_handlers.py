from client.controller.client_controller import login_user, register_user

def register_event_handlers(socketio):
    socketio.on_event('login', login_user)
    socketio.on_event('register', register_user)