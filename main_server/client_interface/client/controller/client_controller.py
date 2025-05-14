from dataclasses import asdict
import requests
from main_server.common.structures import User, Message

database_url = 'http://localhost:5001'

def add_user(data):
    """
    Function to add a user to the database. It performs a post request to the database server with user data.

    Args:
        data (dict): a dictionary containing user data.

    Returns:
        Message: the response from the database server if the request was successful, otherwise a failure message.
    """
    try:
        user = User(**data)
    except TypeError as e:
        return Message.failure(f'Wrong or missing data: {e}').to_dict()
    
    if not user.is_valid:
        return Message.failure('Wrong or missing data').to_dict()
    
    try:
        response = requests.post(f'{database_url}/add_user', json=user.to_dict())
        response.raise_for_status()
        message = Message(**response.json())
        return message.to_dict()
    
    except requests.HTTPError as e:
        return Message.failure(f'Error adding user').to_dict()
    except requests.RequestException as e:
        return Message.failure(f': pippo {e}').to_dict()
    except ValueError:
        return Message.failure('Server response is not valid').to_dict()