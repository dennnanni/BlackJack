"""Player-facing web routes: login, registration, home and dispatch to a
game server. Plain HTTP only: the central server has no Socket.IO.
"""
from dataclasses import dataclass

from flask import Blueprint, redirect, render_template, request, session
from flask_login import UserMixin, current_user, login_required, login_user

from central_server import auth, db, dispatcher
from central_server.config import INITIAL_BALANCE

web_bp = Blueprint('web', __name__)


@dataclass
class UserSession(UserMixin):
    username: str

    def get_id(self):
        return self.username


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
    if user is None or auth.get_hashed_password(password, user.salt) != user.password:
        return render_template('access.html', login=True, error='Wrong username or password')

    login_user(UserSession(username))
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
        return render_template('access.html', register=True, error='Registration failed')
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

    server = dispatcher.pick_server()
    if server is None:
        return _render_home(user, error='No game server is available right now, try again later')

    token = auth.mint_join_token(user.username, user.balance, server.id)
    join_url = f'http://{server.host}:{server.port}/join'
    return render_template('dispatch.html', join_url=join_url, token=token)
