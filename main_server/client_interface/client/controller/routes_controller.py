import base64
import hashlib
import secrets
from client.constants import LOGIN_API_ENDPOINT, LOGIN_PAGE_PATH, REGISTER_API_ENDPOINT, SALT_API_ENDPOINT, USER_HOME_PATH
from client.controller.api_client import get_request, post_request
from client.model.structures import UserSession
from main_server.common.structures import UserLogin, UserDatabase, Message
from flask_login import login_user as flask_login_user


def login_user(username, password):
    print(f'Login attempt with username: {username} and password: {password}')
    if not username or not password:
        return Message.failure('Username and password are required').to_dict()

    salt_response, error = get_request(SALT_API_ENDPOINT, {'username': username})
    if error:
        return error
    
    message = Message(**salt_response)
    salt = message.data.get('salt')
    
    if not salt:
        print('No salt found in response')
        return salt_response  # Could contain error message from server

    hashed_password = get_hashed_password(password, salt)
    login_data = UserLogin(username=username, password=hashed_password).to_dict()

    login_response, error = post_request(LOGIN_API_ENDPOINT, login_data)
    if error:
        return error

    message = Message(**login_response)
    if message.success:
        user = UserSession(username)
        flask_login_user(user)
        return Message.success(redirect=f'{USER_HOME_PATH}{username}').to_dict()
    return message.to_dict()

def register_user(username, password):
    if not username or not password:
        return Message.failure('Username and password are required').to_dict()
    
    hashed_password, salt = generate_hashed_password(password)
    user_db = UserDatabase(username=username, password=hashed_password, salt=salt, balance=0.0)

    register_response, error = post_request(REGISTER_API_ENDPOINT, user_db.to_dict())
    if error:
        return error

    message = Message(**register_response)
    if message.success:
        return Message.success(redirect=f'{LOGIN_PAGE_PATH}').to_dict()
    return message.to_dict()

def get_hashed_password(password, salt):
    salt_bytes = base64.b64decode(salt) if isinstance(salt, str) else salt
    hash_bytes = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, 100_000)
    return base64.b64encode(hash_bytes).decode('utf-8')

def generate_hashed_password(password):
    salt = secrets.token_bytes(16)  # 128-bit salt
    salt_b64 = base64.b64encode(salt).decode('utf-8')
    hashed_password = get_hashed_password(password, salt)
    return hashed_password, salt_b64
