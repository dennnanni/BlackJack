import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from flask import Flask
from flask_socketio import SocketIO

load_dotenv()

SHARED_SECRET = os.getenv('SHARED_SECRET').encode()
if not SHARED_SECRET:
    raise ValueError("SHARED_SECRET environment variable not set")
fernet_shared_secret = Fernet(SHARED_SECRET)

socketio = SocketIO(cors_allowed_origins="*")

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'secret!'
    
    from .routes import register_routes
    register_routes(app)
    
    from .event_handlers import register_event_handlers
    register_event_handlers(socketio)

    socketio.init_app(app)
    return app