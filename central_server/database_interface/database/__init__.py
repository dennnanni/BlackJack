import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL
from flask import Flask
from flask_socketio import SocketIO


url = os.getenv("DATABASE_URL")
if not url:
    url = URL.create(
        drivername="postgresql",
        username="postgres",
        password="postgres",
        host="localhost",
        database="BlackJack"
    )
engine = create_engine(url)
SessionLocal = sessionmaker(bind=engine)


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