import os

from dotenv import load_dotenv

load_dotenv()

SHARED_SECRET = os.getenv('SHARED_SECRET')
if not SHARED_SECRET:
    raise ValueError('SHARED_SECRET is not set: run `python secret_generator.py` first')

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/blackjack')
CENTRAL_PORT = int(os.getenv('CENTRAL_PORT', '5002'))

# Flask session-cookie key
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError('SECRET_KEY is not set in environment file')

# validity period for the join token in seconds
JOIN_TOKEN_TTL = 120
# validity period of the token central sends with its calls to a game server
CENTRAL_TOKEN_TTL = 60

HEARTBEAT = 15

# standby time for reassignment since last heartbeat update
SEAT_TAKEOVER = 30
# validity time without heartbeats for newly assigned seats
SEAT_GRACE = 30

# how long an open buy in may sit with nobody holding its seat before auto closing
BUYIN_GRACE = 240

DEAD_SERVERS_RETENTION = 60 * 60 * 3

TRIMMER_INTERVAL = 120

# how often the trimmer checks that the database answers
DB_PROBE_INTERVAL = 5

# how often the shutdown is sent again to the servers under maintainance
SHUTDOWN_RETRY_INTERVAL = 10

INITIAL_BALANCE = 1000

# credentials of the maintenance panel
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
if not ADMIN_USERNAME or not ADMIN_PASSWORD:
    raise ValueError('ADMIN_USERNAME or ADMIN_PASSWORD is not set: run `python secret_generator.py` first')
