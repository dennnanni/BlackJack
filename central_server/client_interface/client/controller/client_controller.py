from client.constants import JOIN_TABLE_API_ENDPOINT
from client.controller.dispatcher import Dispatcher
from client.utils.security import create_token
from common.response_fields import DATA, ERROR, REDIRECT, TOKEN
from common.structures import UserInfo
from database.model.database_actions import get_user

dispatcher = Dispatcher()

def get_user_info(data):
    username = data.get('username')
    if not username:
        return {ERROR: 'Username is required'}

    user = get_user(username)
    if not user:
        return {ERROR: f'User {username} not found'}

    return {DATA: UserInfo(user.username, user.balance).to_dict()}


def get_game_server(data):
    username = data.get('username')
    if not username:
        return {ERROR: 'Username is required'}

    user_info = get_user_info(data)
    if user_info.get(ERROR) or not user_info.get(DATA):
        return user_info

    balance = user_info.get(DATA).get('balance')
    if float(balance) <= 0:
        return {ERROR: 'User balance is zero, please add funds to play'}

    server, error = dispatcher.pick_game_server()
    if error is not None:
        return {ERROR: error}

    if not server.key:
        raise ValueError(f'Server {server.get_url()} key is not set')

    token = create_token(username, server)

    return {
        REDIRECT: server.get_url() + JOIN_TABLE_API_ENDPOINT,
        TOKEN: token
    }
