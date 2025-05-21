from common.structures import Message, UserLogin
import requests

database_url = 'http://localhost:5001'

def validate_user_login_input(data):
    try:
        user = UserLogin(**data)
        if not user.is_valid:
            return None, Message.failure('Wrong or missing data').to_dict()
        return user, None
    except TypeError as e:
        return None, Message.failure(f'Wrong or missing data: {e}').to_dict()
    
def make_request(method, endpoint, *, params=None, json_data=None):
    """
    Performs a HTTP request to the database server.

    Args:
        method (str): HTTP method ('GET', 'POST', etc.).
        endpoint (str): API path (without base URL).
        params (dict, optional): Query parameters.
        json_data (dict, optional): JSON data to send in request body.

    Returns:
        tuple: (response JSON as dict, error as dict if present)
    """
    url = f'{database_url}/{endpoint}'
    try:
        response = requests.request(method, url, params=params, json=json_data)

        try:
            response_data = response.json()
        except ValueError:
            return None, Message.failure(f'Invalid JSON response from {endpoint}').to_dict()

        if response.ok:
            return response_data, None
        else:
            return None, response_data if isinstance(response_data, dict) else Message.failure(response.reason).to_dict()

    except requests.RequestException as e:
        print(f'Request exception: {e}')
        return None, Message.failure('Something went wrong while contacting the server').to_dict()

    
def get_request(endpoint, params=None):
    """
    Performs a GET request to the database server.

    Args:
        endpoint (str): API path.
        params (dict, optional): Params to include in query string.

    Returns:
        tuple: (JSON response as dict, error as dict if present)
    """
    return make_request('GET', endpoint, params=params)


def post_request(endpoint, json_data):
    """
    Performs a POST request to the database server.

    Args:
        endpoint (str): API path.
        json_data (dict): JSON data to send.

    Returns:
        tuple: (JSON response as dict, error as dict if present)
    """
    return make_request('POST', endpoint, json_data=json_data)
