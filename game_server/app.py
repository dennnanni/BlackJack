import sys
import threading
import time
from http import HTTPStatus
from uuid import uuid4

from flask import Flask
from flask_socketio import SocketIO

from game_server.central_client import client
from game_server.config import (HEARTBEAT_INTERVAL, OUTBOX_PATH, SECRET_KEY,
                                SERVER_HOST, SERVER_PORT)
from game_server.outbox import Outbox

socketio = SocketIO()
outbox = Outbox(OUTBOX_PATH)

# Changes on every start. A restart loses every table
BOOT_ID = uuid4().hex

# Set when central shuts this server down: no new round starts, and each table
# sends its players back to central once its round is over
closing = threading.Event()
# Set once central has been told that nobody is left at our tables
empty_reported = threading.Event()

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
    """Register with central (with retry). On restart, flush pending outbox
    messages under the old ID before reclaiming it."""
    client.server_id = outbox.server_id()
    if client.server_id is not None:
        print(f'[central] restarting: sending the outbox and asking back server id '
              f'{client.server_id}')
    left = outbox.abandon_seats()
    if left:
        print(f'[central] closing the buy ins of {len(left)} players seated before the crash')
    for attempt in range(1, REGISTRATION_ATTEMPTS + 1):
        if _drain_outbox() and _register():
            print(f'[central] registered as server {client.server_id}')
            return True
        print(f'[central] attempt {attempt}/{REGISTRATION_ATTEMPTS} failed, '
              f'retrying in {REGISTRATION_RETRY_SECONDS}s')
        time.sleep(REGISTRATION_RETRY_SECONDS)
    return False


def _heartbeat_loop():
    from game_server.events import seated_players
    while True:
        time.sleep(HEARTBEAT_INTERVAL)
        if client.heartbeat(seated_players()) == HTTPStatus.NOT_FOUND:
            # Central lost our id. register for a new one.
             _register()


def _drain_outbox():
    """Results go first, so the rounds a player finished
    reach central before their buy-in is settled. True if everything was sent."""
    for round_id, results in outbox.pending():
        if not client.send_results(round_id, results):
            return False
        outbox.ack(round_id)
    leaves = outbox.pending_leaves()
    if not leaves:
        return True
    settled = client.close_buy_ins(leaves)
    if settled is None:
        return False
    refused = []
    for buy_in_id in leaves:
        if buy_in_id not in settled:
            refused.append(buy_in_id)
    if refused:
        print(f'[central] buy ins {refused} were not settled: they belong to another server')
    outbox.ack_leaves(leaves)
    return True


def _report_if_empty():
    """After a shutdown, tell central once nobody is seated and every result
    and leave has been delivered, so all the buy-ins are settled by then."""
    from game_server.events import tables_idle
    if not closing.is_set() or empty_reported.is_set() or not tables_idle():
        return
    # With nobody seated, a buy-in still held is one whose player joined but
    # never sat down: central has to close it as well
    outbox.abandon_seats()
    if _drain_outbox() and outbox.is_empty() and client.report_empty():
        empty_reported.set()
        print('[central] every player has left: reported the tables empty')


def _sender_loop():
    """Drain the outbox towards central, retrying on failure."""
    while True:
        _drain_outbox()
        _report_if_empty()
        time.sleep(SEND_RETRY_SECONDS)


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['SESSION_COOKIE_NAME'] = f'game_session_{SERVER_PORT}'

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
