"""HTTP entry point of a game server: the browser lands here after the
central server dispatches a player with a signed join token.
"""
import jwt
from flask import Blueprint, jsonify, render_template, request, session

from game_server.central_client import client
from game_server.config import SHARED_SECRET

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


@game_bp.route('/')
def index():
    return render_template('index.html')


@game_bp.route('/join', methods=['POST'])
def join():
    token = request.form.get('token')
    if not token:
        return jsonify({'error': 'Token is required'}), 400
    try:
        payload = verify_join_token(token, client.server_id)
    except JoinError as e:
        return jsonify({'error': str(e)}), e.status

    # Identity and balance come from the signed token, never from the client.
    session['username'] = payload['sub']
    session['balance'] = float(payload['balance'])
    return render_template('index.html', username=payload['sub'],
                           balance=f"{session['balance']:.2f}")
