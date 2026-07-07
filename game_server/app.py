import sys
import threading
import time

from flask import Flask
from flask_socketio import SocketIO

from game_server.central_client import client
from game_server.config import (HEARTBEAT_INTERVAL, OUTBOX_PATH, SECRET_KEY,
                                SERVER_HOST, SERVER_PORT)
from game_server.outbox import Outbox

socketio = SocketIO()
outbox = Outbox(OUTBOX_PATH)

REGISTRATION_ATTEMPTS = 5
REGISTRATION_RETRY_SECONDS = 2
SEND_RETRY_SECONDS = 2


def _heartbeat_loop():
    """Failure detection: tell central every few seconds that this server is
    alive and how many players it is carrying."""
    from game_server.events import connected_players
    from http import HTTPStatus
    while True:
        time.sleep(HEARTBEAT_INTERVAL)
        status = client.heartbeat(connected_players())
        if status == HTTPStatus.NOT_FOUND:
            # Central lost our registration (e.g. registry reset): re-register.
            client.register(SERVER_HOST, SERVER_PORT)


def _sender_loop():
    """Drain the outbox towards central: at-least-once delivery with retry.

    During a partition send_results fails, the entries stay on disk, and this
    loop simply tries again later; central's round_id ledger makes the
    inevitable duplicates harmless.
    """
    while True:
        for round_id, results in outbox.pending():
            if client.send_results(round_id, results):
                outbox.ack(round_id)
            else:
                break  # central unreachable: back off, retry from the oldest
        time.sleep(SEND_RETRY_SECONDS)


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = SECRET_KEY

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

    threading.Thread(target=_heartbeat_loop, name='heartbeat', daemon=True).start()
    threading.Thread(target=_sender_loop, name='outbox-sender', daemon=True).start()

    return app
