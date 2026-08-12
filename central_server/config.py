import os

from dotenv import load_dotenv

load_dotenv()

SHARED_SECRET = os.getenv('SHARED_SECRET')
if not SHARED_SECRET:
    raise ValueError('SHARED_SECRET is not set: run `python secret_generator.py` first')

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/blackjack')
CENTRAL_PORT = int(os.getenv('CENTRAL_PORT', '5000'))

# validity period for the join token in seconds
JOIN_TOKEN_TTL = 120

INITIAL_BALANCE = 1000
