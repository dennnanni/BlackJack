from flask import Flask, redirect
from flask_login import LoginManager
from flask_socketio import SocketIO

from central_server import db, web
from central_server.api import api_bp
from central_server.web import UserSession, web_bp

socketio = SocketIO(cors_allowed_origins="*", manage_session=False)


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'secret!'

    db.init_db()
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'web.login'

    @login_manager.user_loader
    def load_user(username):
        return UserSession(username)

    @login_manager.unauthorized_handler
    def unauthorized():
        return redirect('/login')

    socketio.on_event('get_user_info', web.get_user_info)
    socketio.on_event('get_game_server', web.get_game_server)
    socketio.init_app(app)
    return app
