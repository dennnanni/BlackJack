from flask import Flask
from flask_socketio import SocketIO
from src.central_api import CentralServerAPI
from src.config.settings import SERVER_ID, SERVER_HOST, SERVER_PORT, CENTRAL_SERVER_URL, SHARED_SECRET
from cryptography.fernet import Fernet

socketio = SocketIO(cors_allowed_origins="*")
key = Fernet.generate_key()
central_client = CentralServerAPI(CENTRAL_SERVER_URL, key, SERVER_ID)

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'secret!'
    
    from .routes import register_routes
    register_routes(app)
    
    socketio.init_app(app)
    
    from .event_handlers import register_event_handlers
    register_event_handlers(socketio)

    result = central_client.register_game_server(
        key=SHARED_SECRET,
        host=SERVER_HOST,
        port=SERVER_PORT
    )
    if not result:
        print("[!] Registrazione server centrale fallita")

    return app