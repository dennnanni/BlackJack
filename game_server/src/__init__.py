from flask import Flask
from flask_socketio import SocketIO

socketio = SocketIO(cors_allowed_origins="*")

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'secret!'
    
    from .routes import register_routes
    register_routes(app)
    
    # from .event_handlers import register_event_handlers
    # register_event_handlers(socketio)

    socketio.init_app(app)
    return app