from client.constants import LOGIN_API_ENDPOINT, LOGIN_PAGE_PATH, REGISTER_API_ENDPOINT, SALT_API_ENDPOINT, USER_HOME_PATH
from client.controller.api_client import get_request, post_request
from client.model.structures import UserSession
from client.utils.security import generate_hashed_password, get_hashed_password
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
