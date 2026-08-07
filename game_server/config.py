import os
import secrets

from dotenv import load_dotenv

load_dotenv()

# Address advertised to central at registration: it is the address the
# *browser* uses to reach this game server after dispatch.
SERVER_HOST = os.getenv('SERVER_HOST', '127.0.0.1')
SERVER_PORT = int(os.getenv('SERVER_PORT', '8000'))

CENTRAL_URL = os.getenv('CENTRAL_URL', 'http://localhost:5000')

# Max players this server accepts; reported to central at registration.
CAPACITY = int(os.getenv('CAPACITY', '10'))
HEARTBEAT_INTERVAL = int(os.getenv('HEARTBEAT_INTERVAL', '5'))

# How long this server may keep staking its players' balances without central
# confirming it. Must stay **below** central's SEAT_TAKEOVER_TTL (30 s), so
# this server has stopped before central can give the same players' seats to
# another one; the margin covers one in-flight heartbeat and clock-rate drift.
LEASE_TIMEOUT = int(os.getenv('LEASE_TIMEOUT', '15'))

# On-disk store for round results not yet acknowledged by central.
OUTBOX_PATH = os.getenv('OUTBOX_PATH', 'outbox.db')

SHARED_SECRET = os.getenv('SHARED_SECRET')
if not SHARED_SECRET:
    raise ValueError('SHARED_SECRET is not set: run `python secret_generator.py` first')

# Flask session-cookie key; random per boot unless pinned via the environment.
SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(32))
