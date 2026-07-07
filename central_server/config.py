import os
import secrets

from dotenv import load_dotenv

load_dotenv()

SHARED_SECRET = os.getenv('SHARED_SECRET')
if not SHARED_SECRET:
    raise ValueError('SHARED_SECRET is not set: run `python secret_generator.py` first')

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/blackjack')
CENTRAL_PORT = int(os.getenv('CENTRAL_PORT', '5000'))

# Flask session-cookie key; random per boot unless pinned via the environment.
SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(32))

# Seconds a join token stays valid: long enough for the browser redirect,
# short enough that a leaked token goes stale quickly.
JOIN_TOKEN_TTL = 120

# A game server is considered offline once its last heartbeat is older than
# this (3x the game servers' heartbeat interval, to forgive lost beats).
HEARTBEAT_TTL = int(os.getenv('HEARTBEAT_TTL', '15'))
REAPER_INTERVAL = int(os.getenv('REAPER_INTERVAL', '5'))

INITIAL_BALANCE = 1000
