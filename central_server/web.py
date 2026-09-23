"""Player-facing web routes: login, registration, home and dispatch to a
game server. Plain HTTP only: the central server has no Socket.IO.
"""
from dataclasses import dataclass

from flask import (Blueprint, redirect, render_template, request, session)
from flask_login import (UserMixin, current_user, login_required, login_user, logout_user)

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
    host: str
    port: int
    connected_users: int
    max_users: int

    def get_url(self):
        return f'http://{self.host}:{self.port}'
    

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
        logout_user()
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

    login_user(UserSession(username), remember=True)
    return redirect(f'/user/{username}')


@web_bp.route('/register', methods=['POST'])
def register_post():
    username = request.form.get('username')
    password = request.form.get('password')
    if not username or not password:
        return render_template('access.html', register=True, error='Username and password are required')

    if db.get_user(username) is not None:
        return render_template('access.html', register=True, error=f'Username {username} is already taken')

    hashed_password, salt = auth.generate_hashed_password(password)
    if not db.add_user(username, hashed_password, salt, INITIAL_BALANCE):
        return render_template('access.html', register=True, error=f'Username {username} is already taken')
    return redirect('/login')


@web_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect('/login')


@web_bp.route('/play', methods=['POST'])
@login_required
def play():
    user = db.get_user(current_user.username)
    if user is None:
        logout_user()
        return redirect('/login')
    if user.balance <= 0:
        return _render_home(user, error='Your balance is zero: add funds to play')

    buy_in = request.form.get('buy_in', type=int)
    if buy_in is None:
        return _render_home(user, error='Enter how much you want to bring to the table')

    available_servers = db.get_alive_servers()
    if not available_servers:
        return _render_home(user, error='No game server is available right now, try again later')

    chosen_server = min(available_servers, key=lambda s: s.load)
    try:
        buy_in_id, reserved = db.create_buy_in(user.username, chosen_server.id, buy_in)
    except ValueError as e:
        return _render_home(user, error=str(e))

    if not db.take_seat(user.username, chosen_server.id):
        # give the money back to the user if it cannot take a seat
        db.close_buy_in(chosen_server.id, [buy_in_id])
        return _render_home(user, error="You are already seated at a table: leave it "
                                        "(or wait a few seconds) before playing again")

    token = auth.create_join_token(user.username, chosen_server.id, buy_in_id, reserved)
    join_url = f'http://{chosen_server.host}:{chosen_server.port}/join'
    return render_template('dispatch.html', join_url=join_url, token=token)
