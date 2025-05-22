import base64
import hashlib
import secrets
import time
import uuid
from client import fernet_shared_secret
import jwt

def create_token(username, server):
    private_key = fernet_shared_secret.decrypt(server.key.encode()).decode()
    
    # token generation to be used for authentication to the game server
    token = {
        'username': username,
        'iat': int(time.time()),
        'exp': int(time.time()) + 120,  # token valid for 2 minutes
        'nonce': str(uuid.uuid4()),
        'server_id': server.id,
        'server_ip': server.ip,
        'server_port': server.port,
    }
    
    return jwt.encode(token, private_key, algorithm='HS256')

def get_hashed_password(password, salt):
    salt_bytes = base64.b64decode(salt) if isinstance(salt, str) else salt
    hash_bytes = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, 100_000)
    return base64.b64encode(hash_bytes).decode('utf-8')

def generate_hashed_password(password):
    salt = secrets.token_bytes(16)  # 128-bit salt
    salt_b64 = base64.b64encode(salt).decode('utf-8')
    hashed_password = get_hashed_password(password, salt)
    return hashed_password, salt_b64
