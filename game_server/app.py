import sys
import time

from flask import Flask
from flask_socketio import SocketIO

from game_server.central_client import client
from game_server.config import SERVER_HOST, SERVER_PORT

socketio = SocketIO()

REGISTRATION_ATTEMPTS = 5
REGISTRATION_RETRY_SECONDS = 2


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'secret!'

    from game_server.join import game_bp
    app.register_blueprint(game_bp)

    socketio.init_app(app)

    # Service discovery with retry: central may be down or partitioned at boot.
    for attempt in range(1, REGISTRATION_ATTEMPTS + 1):
        if client.register(SERVER_HOST, SERVER_PORT):
            print(f'[central] registered as server {client.server_id}')
            break
        print(f'[central] registration attempt {attempt}/{REGISTRATION_ATTEMPTS} failed, '
              f'retrying in {REGISTRATION_RETRY_SECONDS}s')
        time.sleep(REGISTRATION_RETRY_SECONDS)
    else:
        print('[central] could not register: shutting down')
        sys.exit(1)

    from game_server.events import register_event_handlers
    register_event_handlers(socketio)

    return app
