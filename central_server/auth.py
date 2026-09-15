"""Password hashing and the tokens central hands out."""
import base64
import hashlib
import secrets
import time

import jwt
from central_server.config import JOIN_TOKEN_TTL, SHARED_SECRET
from shared.messages import TYP, TYP_JOIN, TYP_SERVER


def create_join_token(username, balance, server_id):
    now = int(time.time())
    # token generation to be used for authentication to the game server
    token = {
        'sub': username,
        'balance': float(balance),
        'typ': TYP_JOIN,
        'iat': now,
        'exp': now + JOIN_TOKEN_TTL,  # add token validity period
        'server_id': server_id
    }

    return jwt.encode(token, SHARED_SECRET, algorithm='HS256')

def verify_server_token(auth_header):
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    try: 
        payload = jwt.decode(auth_header[7:], SHARED_SECRET, algorithms=['HS256'])
    except:
        return None

    return payload if payload.get(TYP) == TYP_SERVER else None


def get_hashed_password(password, salt):
    salt_bytes = base64.b64decode(salt) if isinstance(salt, str) else salt
    hash_bytes = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, 100_000)
    return base64.b64encode(hash_bytes).decode('utf-8')

def generate_hashed_password(password):
    salt = secrets.token_bytes(16)
    salt_b64 = base64.b64encode(salt).decode('utf-8')
    hashed_password = get_hashed_password(password, salt)
    return hashed_password, salt_b64
