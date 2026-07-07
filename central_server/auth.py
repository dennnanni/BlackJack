"""The only two crypto mechanisms in the system: PBKDF2 password hashing and
HS256 JWTs signed with the single SHARED_SECRET (join tokens for players,
bearer tokens for game servers).
"""
import base64
import hashlib
import secrets
import time

import jwt

from central_server.config import JOIN_TOKEN_TTL, SHARED_SECRET


def get_hashed_password(password, salt):
    salt_bytes = base64.b64decode(salt) if isinstance(salt, str) else salt
    hash_bytes = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, 100_000)
    return base64.b64encode(hash_bytes).decode('utf-8')


def generate_hashed_password(password):
    salt = secrets.token_bytes(16)
    salt_b64 = base64.b64encode(salt).decode('utf-8')
    return get_hashed_password(password, salt), salt_b64


def mint_join_token(username, balance, server_id):
    """Authorize `username` to enter game server `server_id` carrying `balance`.

    The server_id claim binds the token to one specific game server, so a
    token minted for one server is rejected by every other one.
    """
    now = int(time.time())
    return jwt.encode(
        {'sub': username, 'balance': float(balance), 'server_id': server_id,
         'iat': now, 'exp': now + JOIN_TOKEN_TTL},
        SHARED_SECRET, algorithm='HS256')


def verify_server_token(auth_header):
    """Validate the Bearer JWT a game server attaches to its API calls.

    Returns the token payload, or None if missing, invalid or expired.
    """
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    try:
        return jwt.decode(auth_header[len('Bearer '):], SHARED_SECRET, algorithms=['HS256'])
    except jwt.InvalidTokenError:
        return None
