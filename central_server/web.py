"""Player-facing web routes: login, registration, home and dispatch to a
game server. Plain HTTP only: the central server has no Socket.IO.
"""
from dataclasses import dataclass

from flask import Blueprint, redirect, render_template, request
from flask_login import (UserMixin, current_user, login_required, login_user,
                         logout_user)

from central_server import auth, db
from central_server.config import (HEARTBEAT_TTL, INITIAL_BALANCE,
                                   SEAT_TAKEOVER_TTL)

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
    if user is None or auth.get_hashed_password(password, user.salt) != user.password:
        return render_template('access.html', login=True, error='Wrong username or password')

    # remember=True: the login outlives the browser being closed, so a player
    # coming back to central from a game server is still who they were.
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
    db.add_user(username, hashed_password, salt, INITIAL_BALANCE)
    return redirect('/login')


@web_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    # logout_user(), not session.clear(): remember=True sets a separate
    # remember_token cookie that would log the player straight back in, and
    # only logout_user() deletes it. It clears the session keys too — and a
    # session.clear() *after* it would wipe the flag that drops the cookie.
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

    # Least-connections dispatch over the servers whose heartbeats are fresh
    # and that still have free seats.
    live = db.get_live_servers(HEARTBEAT_TTL)
    if not live:
        return _render_home(user, error='No game server is available right now, try again later')

    server = min(live, key=lambda s: s.load)

    # One account, one table: claim the player's single seat before minting a
    # token for it, so the same balance cannot be staked on two servers at once.
    if not db.take_seat(user.username, server.id, SEAT_TAKEOVER_TTL):
        return _render_home(user, error='You are already seated at a table: leave it '
                                        '(or wait a few seconds) before playing again')

    token = auth.mint_join_token(user.username, user.balance, server.id)
    join_url = f'http://{server.host}:{server.port}/join'
    return render_template('dispatch.html', join_url=join_url, token=token)
