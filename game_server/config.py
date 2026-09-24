import os

from dotenv import load_dotenv

load_dotenv()


SERVER_HOST = os.getenv('SERVER_HOST', '127.0.0.1')
SERVER_PORT = int(os.getenv('SERVER_PORT', '8000'))

# Base url only, no path: central_client adds its own.
CENTRAL_URL = os.getenv('CENTRAL_URL', 'http://localhost:5002')

# How many players we'll seat. Central uses it to decide where to send people.
CAPACITY = int(os.getenv('CAPACITY', '10'))

# In compose CENTRAL_URL is a docker hostname the browser can't resolve.
CENTRAL_PUBLIC_URL = os.getenv('CENTRAL_PUBLIC_URL', CENTRAL_URLS[0])

HEARTBEAT_INTERVAL = int(os.getenv('HEARTBEAT_INTERVAL', '5'))

# How long we keep staking players' money without hearing from central. Must
# stay below central's SEAT_TAKEOVER (30s), so we've stopped before it can
# hand the same players to another server.
LEASE_TIMEOUT = int(os.getenv('LEASE_TIMEOUT', '15'))

OUTBOX_PATH = os.getenv('OUTBOX_PATH', 'outbox.db')

SHARED_SECRET = os.getenv('SHARED_SECRET')
if not SHARED_SECRET:
    raise ValueError('SHARED_SECRET is not set: run `python secret_generator.py` first')

SECRET_KEY = os.getenv('GAME_SECRET_KEY')
if not SECRET_KEY:
    raise ValueError('GAME_SECRET_KEY is not set: run `python secret_generator.py` first')
