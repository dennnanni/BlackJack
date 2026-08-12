from client.constants import INITIAL_BALANCE, LOGIN_API_ENDPOINT, LOGIN_PAGE_PATH, REGISTER_API_ENDPOINT, SALT_API_ENDPOINT, USER_HOME_PATH
from client.model.structures import UserSession
from client.utils.security import generate_hashed_password, get_hashed_password
from common.http_requests import get_request, post_request
from common.response_fields import ERROR, REDIRECT, SALT, SUCCESS
from client import DATABASE_URL
from common.structures import UserLogin, UserDatabase
from flask_login import login_user as flask_login_user


def login_user(username, password):
    if not username or not password:
        return {ERROR: 'Username and password are required'}

    salt_response = get_request(DATABASE_URL, SALT_API_ENDPOINT, {'username': username})
    if salt_response.get(ERROR):
        return salt_response
    
    salt = salt_response.get(SALT)
    
    if not salt:
        return {ERROR: f'Salt not found for user {username}'}

    hashed_password = get_hashed_password(password, salt)
    login_data = UserLogin(username=username, password=hashed_password).to_dict()

    login_response = post_request(DATABASE_URL, LOGIN_API_ENDPOINT, login_data)
    if login_response.get(ERROR):
        return login_response

    if login_response.get(SUCCESS):
        user = UserSession(username)
        flask_login_user(user)
        return {REDIRECT: f'{USER_HOME_PATH}{username}'}
    
    return {ERROR: 'Login failed'}
    

def register_user(username, password):
    if not username or not password:
        return {ERROR: 'Username and password are required'}
    
    hashed_password, salt = generate_hashed_password(password)
    user_db = UserDatabase(username=username, password=hashed_password, salt=salt, balance=INITIAL_BALANCE)

    register_response = post_request(DATABASE_URL, REGISTER_API_ENDPOINT, user_db.to_dict())
    if register_response.get(ERROR):
        return register_response

    if register_response.get(SUCCESS):
        return {REDIRECT: f'{LOGIN_PAGE_PATH}'}
    
    return {ERROR: 'Registration failed'}
