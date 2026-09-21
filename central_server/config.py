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

# validity period for the join token in seconds
JOIN_TOKEN_TTL = 120

HEARTBEAT = 15

# standby time for reassignment since last heartbeat update
SEAT_TAKEOVER = 30
# validity time without heartbeats for newly assigned seats
SEAT_GRACE = 30

# how long an open buy in may sit with nobody holding its seat before auto closing
BUYIN_GRACE = 120

TRIMMER_INTERVAL = 60 * 10 # 10 minutes

INITIAL_BALANCE = 1000
