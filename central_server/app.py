from flask import Flask, redirect
from flask_login import LoginManager

from central_server import db
from central_server.api import api_bp
from central_server.config import SECRET_KEY
from central_server.web import UserSession, web_bp


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = SECRET_KEY

    db.init_db()
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(username):
        return UserSession(username) if db.get_user(username) else None

    @login_manager.unauthorized_handler
    def unauthorized():
        return redirect('/login')

    return app
