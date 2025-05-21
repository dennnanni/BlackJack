from client.constants import USER_INFO_API_ENDPOINT
from client.controller.dispatcher import Dispatcher
from client.controller.api_client import get_request
from main_server.common.structures import Message, Server

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
    server, error = dispatcher.pick_game_server()
    if error:
        return error
    
    return Message.success(redirect=server.get_url()).to_dict()
    