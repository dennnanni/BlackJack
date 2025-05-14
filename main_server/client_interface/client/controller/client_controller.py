from dataclasses import asdict
import requests
from main_server.common.structures import User, Message

database_url = 'http://localhost:5001'

def add_user(data):
    print("Received request to add user")
    try:
        user = User(**data)
    except TypeError as e:
        return Message(False, f'Wrong or missing data: {e}').to_dict()
    
    if not user.is_valid:
        return Message(False, 'Wrong or missing data').to_dict()
    
    try:
        response = requests.post(f'{database_url}/add_user', json=user.to_dict())
        response.raise_for_status()
        message = Message(**response.json())
        return message.to_dict()
    except requests.HTTPError as e:
        return Message(False, f'Error adding user').to_dict()
    except requests.RequestException as e:
        return Message(False, f': pippo {e}').to_dict()
    except ValueError:
        return Message(False, 'Server response is not valid').to_dict()