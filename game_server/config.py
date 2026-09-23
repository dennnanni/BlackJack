import os

from dotenv import load_dotenv

load_dotenv()

# What we tell central at registration. The browser connects here too, so it
# can't be an address only central can reach.
SERVER_HOST = os.getenv('SERVER_HOST', '127.0.0.1')
SERVER_PORT = int(os.getenv('SERVER_PORT', '8000'))

# Comma separated list of central replicas.
CENTRAL_URLS = os.getenv('CENTRAL_URLS', 'http://localhost:5002').split(',')

# How many players we'll seat. Central uses it to decide where to send people.
CAPACITY = int(os.getenv('CAPACITY', '10'))

# In compose CENTRAL_URL is a docker hostname the browser can't resolve.
CENTRAL_PUBLIC_URL = os.getenv('CENTRAL_PUBLIC_URL', CENTRAL_URLS[0])

HEARTBEAT_INTERVAL = int(os.getenv('HEARTBEAT_INTERVAL', '5'))

# How long we keep staking players' money without hearing from central. Must
# stay below central's SEAT_TAKEOVER_TTL (30s), so we've stopped before it can
# hand the same players to another server.
LEASE_TIMEOUT = int(os.getenv('LEASE_TIMEOUT', '15'))

OUTBOX_PATH = os.getenv('OUTBOX_PATH', 'outbox.db')

SHARED_SECRET = os.getenv('SHARED_SECRET')
if not SHARED_SECRET:
    raise ValueError('SHARED_SECRET is not set: run `python secret_generator.py` first')
