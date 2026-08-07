from flask import Flask, redirect
from flask_login import LoginManager

from central_server import db
from central_server.api import api_bp
from central_server.config import SECRET_KEY
from central_server.reaper import start_reaper
from central_server.web import UserSession, web_bp


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = SECRET_KEY
    # Cookies are scoped to a host, *not* to a port: central and the game
    # servers all live on localhost in a demo, so a shared cookie name would
    # have them overwriting each other's session — joining a table would log
    # the player out of central. Every process gets its own name.
    app.config['SESSION_COOKIE_NAME'] = 'central_session'

    db.init_db()
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)
    start_reaper()

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(username):
        return UserSession(username) if db.get_user(username) else None

    @login_manager.unauthorized_handler
    def unauthorized():
        return redirect('/login')

    return app
