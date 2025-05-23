from tkinter import E
from client.utils.security import create_token
from client.constants import PLAYING_API_ENDPOINT, USER_INFO_API_ENDPOINT
from client.controller.dispatcher import Dispatcher
from common.http_requests import get_request
from common.response_fields import ERROR, REDIRECT, TOKEN
from common.structures import RegisteredServer
from servers import DATABASE_URL

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
    
    user_status = get_request(DATABASE_URL, PLAYING_API_ENDPOINT, {'username': username})
    
    if user_status.get(ERROR):
        return user_status
    
    server, error = dispatcher.pick_game_server()
    if error is not None:
        return {ERROR: server}
    
    if not server.key:
        raise ValueError(f'Server {server.get_url()} key is not set')
    
    token = create_token(username, server)
    
    return {
        REDIRECT: server.get_url(),
        TOKEN: token
    }    