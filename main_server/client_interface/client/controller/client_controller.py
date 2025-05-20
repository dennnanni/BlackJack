from client.controller.api_client import get_request
from main_server.common.structures import Message
from client.controller.api_client import db_api_routes


def get_user_info(data):
    username = data.get('username')
    if not username:
        return Message.failure('Username is required').to_dict()

    user_info_response, error = get_request(db_api_routes['get_user_info'], {'username': username})
    if error:
        return error
    
    return user_info_response
    

def get_game_server(data):
    # load_balancer.get_server()
    # response = post_request(routes['assign_user'], {'username': username, 'server_id': server})
    return Message.success(redirect='http://localhost:4999').to_dict()
    