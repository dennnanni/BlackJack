from central_server.utils.security import create_token
from central_server.constants.client_constants import JOIN_TABLE_API_ENDPOINT
from central_server.controller.client.dispatcher import Dispatcher
from central_server.constants.response_fields import DATA, ERROR, REDIRECT, TOKEN
import central_server.controller.database.database_controller as database

dispatcher = Dispatcher()

def get_user_info(data):
    username = data.get('username')
    if not username:
        return {ERROR: 'Username is required'}

    user_info = database.get_user_info(username)    

    if isinstance(user_info, str):
        return {ERROR: user_info}

    return {DATA: user_info.to_dict()}

def get_game_server(data):
    print('Requesting game server')
    username = data.get('username')
    if not username:
        return {ERROR: 'Username is required'}
    
    user_info = database.get_user_info(username)
    if user_info.get(ERROR) or not user_info.get(DATA):
        return user_info
    
    balance = user_info.get(DATA).get('balance')
    if float(balance) <= 0:
        return {ERROR: 'User balance is zero, please add funds to play'}
    
    user_status = database.user_playing(username)
    
    if isinstance(user_status, str):
        return {ERROR: user_status}
    
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