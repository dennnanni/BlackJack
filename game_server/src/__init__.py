import time
from flask import Flask
from flask_socketio import SocketIO
from src.central_api import CentralServerAPI
from src.config.settings import SERVER_HOST, SERVER_PORT, CENTRAL_SERVER_URL, SHARED_SECRET
from cryptography.fernet import Fernet

socketio = SocketIO(cors_allowed_origins="*")
key = Fernet.generate_key()
central_client = CentralServerAPI(CENTRAL_SERVER_URL)

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'secret!'
    
    from .routes import register_routes
    register_routes(app)
    
    socketio.init_app(app)
        
    # TODO: possibilità di avere una lista di server da contattare in caso di partizionamento di rete
    for i in range(5):
        result = central_client.register_game_server(
            host=SERVER_HOST,
            port=SERVER_PORT,
            shared_key=SHARED_SECRET,
            new_key=key
        )
        if result:
            break
        print(f"Attempt {i+1}: registration failed, retry in 2s...")
        time.sleep(2)
    else:
        print("[!] Failed to register the game server after 10 attempts. Shutting down.")
        exit(1)
    
    from .event_handlers import register_event_handlers
    register_event_handlers(socketio)

    return app