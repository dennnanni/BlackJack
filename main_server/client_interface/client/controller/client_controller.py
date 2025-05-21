import random
import time
import jwt
from client import SHARED_SECRET, fernet_shared_secret
from client.constants import USER_INFO_API_ENDPOINT
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
    server, error = dispatcher.pick_game_server()
    if error:
        return error
    
    if not server.key:
        raise ValueError("Server key is not set")
    
    private_key = fernet_shared_secret.decrypt(server.key.encode()).decode()
    
    # token generation to be used for authentication to the game server
    token = {
        'username': data.get('username'),
        'iat': int(time.time()),
        'exp': int(time.time()) + 120,  # token valid for 2 minutes
        'nonce': random.randint(0, 1000000),
        'server_id': server.id,
        'server_ip': server.ip,
        'server_port': server.port,
    }
    
    jwt_token = jwt.encode(token, private_key, algorithm='HS256')
    
    return Message.success(redirect=server.get_url(), data={'token': jwt_token}).to_dict()
    