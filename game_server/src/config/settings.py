import os
from dotenv import load_dotenv

load_dotenv()  # carica variabili da .env

SERVER_ID = os.getenv("SERVER_ID", "default_server")
SERVER_HOST = os.getenv("SERVER_HOST", "localhost")
SERVER_PORT = int(os.getenv("SERVER_PORT", 5000))

CENTRAL_SERVER_URL = os.getenv("CENTRAL_SERVER_URL", "http://localhost:8000")

SHARED_SECRET = os.getenv("SHARED_SECRET")
if not SHARED_SECRET:
    raise ValueError("SHARED_SECRET non impostata nel .env")

SHARED_SECRET = SHARED_SECRET.encode()  # serve in byte per Fernet
