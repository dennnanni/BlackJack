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
from shared.messages import TYP, TYP_JOIN, TYP_SERVER


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
    token minted for one server is rejected by every other one. The typ claim
    keeps it out of the server-to-server API: this token is handed to a
    browser, so without it any player could replay their own dispatch token
    against /api/servers/results and credit themselves anything they liked.
    """
    now = int(time.time())
    return jwt.encode(
        {TYP: TYP_JOIN, 'sub': username, 'balance': float(balance),
         'server_id': server_id, 'iat': now, 'exp': now + JOIN_TOKEN_TTL},
        SHARED_SECRET, algorithm='HS256')


def verify_server_token(auth_header):
    """Validate the Bearer JWT a game server attaches to its API calls.

    Returns the token payload, or None if missing, invalid, expired or not a
    *server* token. Checking the class is not optional: both kinds of token
    are HS256 over the same secret, and a join token also carries a server_id,
    so a signature check alone would accept one from any logged-in player.
    """
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    try:
        payload = jwt.decode(auth_header[len('Bearer '):], SHARED_SECRET, algorithms=['HS256'])
    except jwt.InvalidTokenError:
        return None
    return payload if payload.get(TYP) == TYP_SERVER else None
