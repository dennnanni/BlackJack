import os
from dotenv import load_dotenv

load_dotenv()  # carica variabili da .env

SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", 5000))
CENTRAL_SERVER_URL = os.getenv("CENTRAL_SERVER_URL", "http://localhost:5002")

SHARED_SECRET = os.getenv("SHARED_SECRET")
if not SHARED_SECRET:
    raise ValueError("SHARED_SECRET non impostata nel .env")

