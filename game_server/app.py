import sys
import threading
import time
from http import HTTPStatus

from flask import Flask
from flask_socketio import SocketIO

from game_server.central_client import client
from game_server.config import (HEARTBEAT_INTERVAL, OUTBOX_PATH, SERVER_HOST,
                                SERVER_PORT)
from game_server.outbox import Outbox

socketio = SocketIO()
outbox = Outbox(OUTBOX_PATH)

REGISTRATION_ATTEMPTS = 5
REGISTRATION_RETRY_SECONDS = 2
SEND_RETRY_SECONDS = 2


def _register():
    """Register with central, which gives us back the id we already hold if
    it still knows it."""
    if not client.register(SERVER_HOST, SERVER_PORT):
        return False
    outbox.save_server_id(client.server_id)
    return True


def _join_central():
    """Register with central, retrying a few times since it may not be up yet.
    If we had an id before a restart, ask central for the same one."""
    client.server_id = outbox.server_id()
    if client.server_id is not None:
        print(f'[central] restarting: asking back server id {client.server_id}')
    for attempt in range(1, REGISTRATION_ATTEMPTS + 1):
        if _register():
            print(f'[central] registered as server {client.server_id}')
            return True
        print(f'[central] registration attempt {attempt}/{REGISTRATION_ATTEMPTS} failed, '
              f'retrying in {REGISTRATION_RETRY_SECONDS}s')
        time.sleep(REGISTRATION_RETRY_SECONDS)
    return False


def _heartbeat_loop():
    from game_server.events import seated_players
    while True:
        time.sleep(HEARTBEAT_INTERVAL)
        if client.heartbeat(seated_players()) == HTTPStatus.NOT_FOUND:
            # Central forgot our registration (a registry reset, say): the
            # players' seats are gone with it, so claim a new id and carry on.
            _register()


def _drain_outbox():
    """Results go first, so the rounds a player finished
    reach central before their buy-in is settled."""
    for round_id, results in outbox.pending():
        if not client.send_results(round_id, results):
            return
        outbox.ack(round_id)
    leaves = outbox.pending_leaves()
    if not leaves:
        return
    settled = client.close_buy_ins(leaves)
    if settled is None:
        return
    refused = []
    for buy_in_id in leaves:
        if buy_in_id not in settled:
            refused.append(buy_in_id)
    if refused:
        print(f'[central] buy ins {refused} were not settled: they belong to another server')
    outbox.ack_leaves(leaves)


def _sender_loop():
    """Drain the outbox towards central, retrying on failure."""
    while True:
        _drain_outbox()
        time.sleep(SEND_RETRY_SECONDS)


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'secret!'

    from game_server.join import game_bp
    app.register_blueprint(game_bp)

    socketio.init_app(app)

    if not _join_central():
        print('[central] could not register: shutting down')
        sys.exit(1)

    from game_server.events import register_event_handlers
    register_event_handlers(socketio)

    threading.Thread(target=_heartbeat_loop, name='heartbeat', daemon=True).start()
    threading.Thread(target=_sender_loop, name='outbox-sender', daemon=True).start()

    return app
