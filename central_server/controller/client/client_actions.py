from central_server.constants.client_constants import INITIAL_BALANCE, LOGIN_PAGE_PATH, USER_HOME_PATH
from central_server.model.structures import UserSession
from central_server.utils.security import generate_hashed_password, get_hashed_password
from central_server.constants.response_fields import ERROR, REDIRECT
from flask_login import login_user as flask_login_user
import central_server.controller.database.database_controller as database


def login_user(username, password):
    print(f'Login attempt with username: {username} and password: {password}')
    if not username or not password:
        return {ERROR: 'Username and password are required'}

    salt, error = database.get_salt(username)
    print(f'Retrieved salt for username {username}: {salt}')
    if error:
        return {ERROR: error}
    
    if not salt:    
        return {ERROR: f'Salt not found for user {username}'}

    hashed_password = get_hashed_password(password, salt)

    login = database.login_user(username, hashed_password)
    print(f'Login result for username {username}: {login}')
    if isinstance(login, str):
        return {ERROR: login}

    if login is True:
        user = UserSession(username)
        flask_login_user(user)
        return {REDIRECT: f'{USER_HOME_PATH}{username}'}
    
    return {ERROR: 'Login failed'}
    

def register_user(username, password):
    if not username or not password:
        return {ERROR: 'Username and password are required'}
    
    hashed_password, salt = generate_hashed_password(password)

    registration = database.register_user(username, hashed_password, salt, INITIAL_BALANCE)
    if isinstance(registration, str):
        return {ERROR: registration}

    if registration is True:
        return {REDIRECT: f'{LOGIN_PAGE_PATH}'}
    
    return {ERROR: 'Registration failed'}
