"""Tells the game servers under maintainance to shut down.
"""
import logging
import threading
import time

import requests

from central_server import auth, db
from central_server.config import SHUTDOWN_RETRY_INTERVAL

SHUTDOWN_PATH = '/api/shutdown'
SHUTDOWN_TIMEOUT = 3

logger = logging.getLogger(__name__)


def _address(server):
    return server.internal_url or f'http://{server.host}:{server.port}'


def send_shutdown(server):
    """True once the game server accepted the shutdown."""
    try:
        response = requests.post(
            f'{_address(server)}{SHUTDOWN_PATH}',
            headers={'Authorization': f'Bearer {auth.create_central_token(server.id)}'},
            timeout=SHUTDOWN_TIMEOUT)
    except requests.RequestException as e:
        logger.warning(f'shutdown of server {server.id} failed: {e}')
        return False
    if response.status_code != 202:
        logger.warning(f'shutdown of server {server.id} refused: {response.status_code}')
        return False
    return True


def _run():
    while True:
        time.sleep(SHUTDOWN_RETRY_INTERVAL)
        try:
            for server in db.get_servers_to_shut_down():
                send_shutdown(server)
        except Exception:
            logger.exception('sending the shutdowns failed')


def start_shutdown_sender():
    threading.Thread(target=_run, name='shutdown-sender', daemon=True).start()
