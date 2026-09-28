"""HTTP entry point of a game server: the browser lands here after the
central server dispatches a player with a signed join token.
"""
import jwt
from flask import (Blueprint, jsonify, redirect, render_template, request,
                   session, url_for)

from game_server.central_client import client
from game_server.config import CENTRAL_PUBLIC_URL, SHARED_SECRET
from game_server.runtime import BOOT_ID, closing, outbox, socketio
from shared.messages import BUY_IN, BUY_IN_ID, SERVER_ID, TYP, TYP_CENTRAL, TYP_JOIN

game_bp = Blueprint('game', __name__)


class JoinError(Exception):
    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


def verify_token(token, typ, expected_server_id):
    """Decode and validate a token minted by the central server."""
    try:
        payload = jwt.decode(token, SHARED_SECRET, algorithms=['HS256'])
    except jwt.InvalidTokenError as e:
        raise JoinError(f'Invalid token: {e}', 401)
    
    if payload.get(TYP) != typ:
        raise JoinError(f'Not a {typ} token', 401)
    if payload.get(SERVER_ID) != expected_server_id:
        raise JoinError('Token was minted for a different server', 403)
    return payload


def verify_join_token(token, expected_server_id):
    """A join token must also carry the buy-in the player brings."""
    payload = verify_token(token, TYP_JOIN, expected_server_id)
    if payload.get(BUY_IN_ID) is None or payload.get(BUY_IN) is None:
        raise JoinError('Token carries no buy-in', 401)
    return payload


@game_bp.route('/')
def index():
    # The table page lives at a GET url so reloading it is always safe: the
    # identity comes from the session that /join stored.
    username = session.get('username')
    if username is None:
        return render_template('index.html')

    from game_server.events import can_take_seat, user_map   # circular at import time
    user = user_map.get(username)
    if user is None and not can_take_seat(session.get('buy_in_id'), session.get('join_exp', 0),
                                          session.get('boot_id')):
        # Not seated and the buy-in cannot seat them any more: it has been
        # settled, and only central can open a new one.
        session.clear()
        return redirect(CENTRAL_PUBLIC_URL)
    balance = user.balance if user else session['balance']
    return render_template('index.html', username=username,
                           balance=f"{balance:.2f}",
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
    """Take in a join token, then redirect to the table page, whose socket
    takes the seat."""

    token = request.form.get('token')
    try:
        if not token:
            raise JoinError('Token is required', 400)
        payload = verify_join_token(token, client.server_id)
    except JoinError as e:
        return jsonify({'error': str(e)}), e.status

    # we don't seat new players while the server is closing
    if closing.is_set():
        outbox.enqueue_leave(payload[BUY_IN_ID])
        return redirect(CENTRAL_PUBLIC_URL)

    # Identity and money come from the signed token, never from the client.
    # The player brings the buy-in, not their whole balance; join_exp bounds
    # how long that buy-in may still take a seat.
    session['username'] = payload['sub']
    session['buy_in_id'] = payload[BUY_IN_ID]
    session['balance'] = float(payload[BUY_IN])
    session['join_exp'] = payload['exp']
    session['boot_id'] = BOOT_ID
    session.permanent = True
    # Held from now on, not from when the socket sits down: if we crash in
    # between, the restart still has to close this buy-in.
    outbox.seat(payload[BUY_IN_ID])
    return redirect(url_for('game.index'))


@game_bp.route('/api/shutdown', methods=['POST'])
def shutdown():
    """Central shuts this server down: each table ends the round in progress,
    then sends its players back. The server stays up, taking nobody, until it
    restarts."""
    auth_header = request.headers.get('Authorization', '')
    try:
        if not auth_header.startswith('Bearer '):
            raise JoinError('Token is required', 401)
        verify_token(auth_header.removeprefix('Bearer '), TYP_CENTRAL, client.server_id)
    except JoinError as e:
        return jsonify({'error': str(e)}), e.status

    if not closing.is_set():
        print('[central] shutdown ordered: finishing the rounds in progress')
        closing.set()
        socketio.emit('server_closing', {})
    return '', 202
