from client.utils.security import create_token
from client.constants import PLAYING_API_ENDPOINT, USER_INFO_API_ENDPOINT
from client.controller.dispatcher import Dispatcher
from client.controller.api_client import get_request
from main_server.common.structures import Message

dispatcher = Dispatcher()

def get_user_info(data):
    username = data.get('username')
    if not username:
        return Message.failure('Username is required').to_dict()

    user_info_response, error = get_request(USER_INFO_API_ENDPOINT, {'username': username})
    if error:
        return error
    
    return user_info_response
    

def get_game_server(data):
    print('Requesting game server')
    username = data.get('username')
    if not username:
        return Message.failure('Username is required').to_dict()
    
    user_status, error = get_request(PLAYING_API_ENDPOINT, {'username': username})
    if error:
        return error
    message = Message(**user_status)
    if not message.success:
        return message.to_dict()
    
    server, error = dispatcher.pick_game_server()
    if error:
        return error
    
    if not server.key:
        raise ValueError("Server key is not set")
    
    token = create_token(username, server)
    
    return Message.success(redirect=server.get_url(), data={'token': token}).to_dict()
    