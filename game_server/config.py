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

SHARED_SECRET = os.getenv('SHARED_SECRET')
if not SHARED_SECRET:
    raise ValueError('SHARED_SECRET is not set: run `python secret_generator.py` first')

# Flask session-cookie key; random per boot unless pinned via the environment.
SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(32))
