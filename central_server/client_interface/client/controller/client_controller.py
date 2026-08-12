from client.utils.security import create_token
from client.constants import JOIN_TABLE_API_ENDPOINT, PLAYING_API_ENDPOINT, USER_INFO_API_ENDPOINT
from client.controller.dispatcher import Dispatcher
from common.http_requests import get_request
from common.response_fields import DATA, ERROR, REDIRECT, TOKEN
from client import DATABASE_URL

dispatcher = Dispatcher()

def get_user_info(data):
    username = data.get('username')
    if not username:
        return {ERROR: 'Username is required'}

    user_info_response = get_request(DATABASE_URL, USER_INFO_API_ENDPOINT, {'username': username})
    
    return user_info_response
    

def get_game_server(data):
    print('Requesting game server')
    username = data.get('username')
    if not username:
        return {ERROR: 'Username is required'}
    
    user_info = get_user_info(data)
    if user_info.get(ERROR) or not user_info.get(DATA):
        return user_info
    
    balance = user_info.get(DATA).get('balance')
    if float(balance) <= 0:
        return {ERROR: 'User balance is zero, please add funds to play'}
    
    user_status = get_request(DATABASE_URL, PLAYING_API_ENDPOINT, {'username': username})
    
    if user_status.get(ERROR):
        return user_status
    
    server, error = dispatcher.pick_game_server()
    if error is not None:
        return {ERROR: server}
    
    if not server.key:
        raise ValueError(f'Server {server.get_url()} key is not set')
    
    token = create_token(username, server)

    print(server.get_url() + JOIN_TABLE_API_ENDPOINT)
    
    return {
        REDIRECT: server.get_url() + JOIN_TABLE_API_ENDPOINT,
        TOKEN: token
    }    