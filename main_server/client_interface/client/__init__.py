from client.model.structures import UserSession
from flask import Flask, redirect
from flask_socketio import SocketIO
from flask_login import LoginManager

socketio = SocketIO(cors_allowed_origins="*", manage_session=False)

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'secret!'
    
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