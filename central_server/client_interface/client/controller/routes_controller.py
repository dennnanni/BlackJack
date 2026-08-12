from client.constants import INITIAL_BALANCE, LOGIN_PAGE_PATH, USER_HOME_PATH
from client.model.structures import UserSession
from client.utils.security import generate_hashed_password, get_hashed_password
from common.response_fields import ERROR, REDIRECT
from database.model.database_actions import add_user, get_user
from flask_login import login_user as flask_login_user


def login_user(username, password):
    if not username or not password:
        return {ERROR: 'Username and password are required'}

    user = get_user(username)
    if not user:
        return {ERROR: f'User {username} not found'}

    if get_hashed_password(password, user.salt) != user.password:
        return {ERROR: f'Wrong password for user {username}'}

    flask_login_user(UserSession(username))
    return {REDIRECT: f'{USER_HOME_PATH}{username}'}


def register_user(username, password):
    if not username or not password:
        return {ERROR: 'Username and password are required'}

    hashed_password, salt = generate_hashed_password(password)

    if add_user(username, hashed_password, salt, INITIAL_BALANCE) is not True:
        return {ERROR: f'Error adding user {username}'}

    return {REDIRECT: LOGIN_PAGE_PATH}
