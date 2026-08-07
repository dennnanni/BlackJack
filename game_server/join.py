"""HTTP entry point of a game server: the browser lands here after the
central server dispatches a player with a signed join token.
"""
import jwt
from flask import (Blueprint, jsonify, redirect, render_template, request,
                   session, url_for)

from game_server.central_client import client
from game_server.config import CENTRAL_PUBLIC_URL, SHARED_SECRET

game_bp = Blueprint('game', __name__)


class JoinError(Exception):
    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


def verify_join_token(token, expected_server_id):
    """Decode and validate a join token minted by the central server.

    Returns the token payload; raises JoinError if the token is invalid,
    expired, or was minted for a different server.
    """
    try:
        payload = jwt.decode(token, SHARED_SECRET, algorithms=['HS256'])
    except jwt.InvalidTokenError as e:
        raise JoinError(f'Invalid token: {e}', 401)
    if payload.get('server_id') != expected_server_id:
        raise JoinError('Token was minted for a different server', 403)
    return payload


def _live_balance(username):
    """The balance the table is playing with — it moves every round, while the
    session only holds the snapshot the join token carried."""
    from game_server.events import last_balance, user_map
    user = user_map.get(username)
    if user:
        return user.balance
    return last_balance.get(username, session['balance'])


@game_bp.route('/')
def index():
    # The table page lives at a GET url so reloading it is always safe: the
    # identity comes from the session that /join stored, and the socket 'join'
    # handler puts the player back into their room and round.
    username = session.get('username')
    if username is None:
        return render_template('index.html')
    return render_template('index.html', username=username,
                           balance=f"{_live_balance(username):.2f}",
                           central_url=CENTRAL_PUBLIC_URL)


@game_bp.route('/leave', methods=['POST'])
def leave():
    """Give up the seat and go back to central. POST, not a link: it changes
    state, and a prefetched GET must never throw a player off their table."""
    username = session.get('username')
    if username:
        from game_server.events import leave_table
        leave_table(username)
    session.clear()
    return redirect(CENTRAL_PUBLIC_URL)


@game_bp.route('/join', methods=['POST'])
def join():
    """Consume a one-shot join token, then redirect to the table page.

    POST/redirect/GET on purpose: the token is valid for two minutes and can
    only be spent once, so if the *response* to this POST were the table page
    itself, every F5 would re-submit the spent token and answer with an error
    instead of the game. After the redirect the browser sits on `/`, where a
    reload is an ordinary GET.
    """
    token = request.form.get('token')
    try:
        if not token:
            raise JoinError('Token is required', 400)
        payload = verify_join_token(token, client.server_id)
    except JoinError as e:
        # A spent or missing token is harmless for a browser that already
        # holds a session here (a re-submitted dispatch form, a back button):
        # it was let in by a valid token earlier, so send it to its table.
        if session.get('username'):
            return redirect(url_for('game.index'))
        return jsonify({'error': str(e)}), e.status

    # Identity and balance come from the signed token, never from the client.
    session['username'] = payload['sub']
    session['balance'] = float(payload['balance'])
    session.permanent = True

    from game_server.events import last_balance
    last_balance.pop(payload['sub'], None)  # central just told us the truth
    return redirect(url_for('game.index'))
