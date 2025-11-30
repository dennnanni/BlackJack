from client.model.structures import UserSession
from flask import Flask, redirect
from flask_socketio import SocketIO
from flask_login import LoginManager
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL

load_dotenv()

SHARED_SECRET = os.getenv('SHARED_SECRET').encode()
if not SHARED_SECRET:
    raise ValueError('SHARED_SECRET environment variable not set')
fernet_shared_secret = Fernet(SHARED_SECRET)

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError('DATABASE_URL environment variable is not set')

url = None
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

socketio = SocketIO(cors_allowed_origins="*", manage_session=False)

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'secret!'
    app.config['SESSION_PERMANENT'] = False
    
    from .routes import register_routes
    register_routes(app)
    
    from .event_handlers import register_event_handlers
    register_event_handlers(socketio)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'client_interface.login'
    
    @login_manager.user_loader
    def load_user(username):
        return UserSession(username)

    @login_manager.unauthorized_handler
    def unauthorized():
        return redirect('/login') 
    
    socketio.init_app(app)
    return app