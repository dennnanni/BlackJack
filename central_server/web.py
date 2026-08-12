"""Player-facing web routes: login, registration, home and dispatch to a
game server. Plain HTTP only: the central server has no Socket.IO.
"""
from dataclasses import dataclass

from flask import (Blueprint, redirect, render_template, request, session)
from flask_login import (UserMixin, current_user, login_required, login_user)

from central_server import auth, db
from central_server.config import INITIAL_BALANCE

# Path to external API
JOIN_TABLE_API_ENDPOINT = '/join'

web_bp = Blueprint('web', __name__)


@dataclass
class UserSession(UserMixin):
    username: str

    def get_id(self):
        return self.username


@dataclass
class ServerLoad:
    """A registered game server together with how many players it holds."""
    id: int
    ip: str
    port: int
    connected_users: int
    max_users: int
    key: str

    def get_url(self):
        return f'http://{self.ip}:{self.port}'


def _pick_game_server():
    """The least loaded registered game server, or None if there is none."""
    servers = db.get_servers_with_user_count()
    if not servers:
        return None
    return min((ServerLoad(*server) for server in servers),
               key=lambda server: server.connected_users)


def _render_home(user, error=None):
    return render_template('home.html', username=user.username,
                           balance=f'{user.balance:.2f}', error=error)


@web_bp.route('/')
@web_bp.route('/login', methods=['GET'])
def login_page():
    if current_user.is_authenticated:
        return redirect(f'/user/{current_user.username}')
    return render_template('access.html', login=True)


@web_bp.route('/register', methods=['GET'])
def register_page():
    return render_template('access.html', register=True)


@web_bp.route('/user/<username>')
@login_required
def home(username):
    if username != current_user.username:
        return redirect(f'/user/{current_user.username}')
    user = db.get_user(current_user.username)
    if user is None:
        session.clear()
        return redirect('/login')
    return _render_home(user)


@web_bp.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username')
    password = request.form.get('password')
    if not username or not password:
        return render_template('access.html', login=True, error='Username and password are required')

    user = db.get_user(username)
    if user is None:
        return render_template('access.html', login=True, error=f'User {username} not found')
    if auth.get_hashed_password(password, user.salt) != user.password:
        return render_template('access.html', login=True, error=f'Wrong password for user {username}')

    login_user(UserSession(username))
    return redirect(f'/user/{username}')


@web_bp.route('/register', methods=['POST'])
def register_post():
    username = request.form.get('username')
    password = request.form.get('password')
    if not username or not password:
        return render_template('access.html', register=True, error='Username and password are required')

    hashed_password, salt = auth.generate_hashed_password(password)
    if db.add_user(username, hashed_password, salt, INITIAL_BALANCE) is not True:
        return render_template('access.html', register=True, error=f'Error adding user {username}')

    return redirect('/login')


@web_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    return redirect('/login')


@web_bp.route('/play', methods=['POST'])
@login_required
def play():
    user = db.get_user(current_user.username)
    if user is None:
        session.clear()
        return redirect('/login')
    if user.balance <= 0:
        return _render_home(user, error='Your balance is zero: add funds to play')

    server = _pick_game_server()
    if server is None:
        return _render_home(user, error='No game server is available right now, try again later')

    token = auth.create_token(user.username, server)
    return render_template('dispatch.html',
                           join_url=server.get_url() + JOIN_TABLE_API_ENDPOINT,
                           token=token)
