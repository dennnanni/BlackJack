import base64
import hashlib
import secrets
import requests
from main_server.common.structures import UserInfo, UserLogin, UserDatabase, Message

routes = {
    'login': '/login',
    'register': '/register',
    'get_user_info': '/get_user_info',
    'get_salt': '/get_salt',
    'user_homepage': '/user/',
}

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
    PErforms a POST request to the database server.

    Args:
        endpoint (str): API path.
        json_data (dict): JSON data to send.

    Returns:
        tuple: (JSON response as dict, error as dict if present)
    """
    return make_request('POST', endpoint, json_data=json_data)

def login_user(data):
    user, error = validate_user_login_input(data)
    if error:
        return error

    salt_response, error = post_request(routes['get_salt'], user.username)
    if error:
        return error
    
    message = Message(**salt_response)
    salt = message.data.get('salt')
    
    if not salt:
        print('No salt found in response')
        return salt_response  # Could contain error message from server

    hashed_password = get_hashed_password(user.password, salt)
    login_data = UserLogin(username=user.username, password=hashed_password).to_dict()

    login_response, error = post_request(routes['login'], login_data)
    if error:
        return error

    message = Message(**login_response)
    if message.success:
        return Message.success(redirect=f'{routes['user_homepage']}{user.username}').to_dict()
    return message.to_dict()

def register_user(data):
    user, error = validate_user_login_input(data)
    if error:
        return error

    hashed_password, salt = generate_hashed_password(user.password)
    user_db = UserDatabase(username=user.username, password=hashed_password, salt=salt, balance=0.0)

    register_response, error = post_request(routes['register'], user_db.to_dict())
    if error:
        return error

    message = Message(**register_response)
    if message.success:
        return Message.success(redirect=f'{routes['register']}{user.username}').to_dict()
    return message.to_dict()

def get_hashed_password(password, salt):
    salt_bytes = base64.b64decode(salt) if isinstance(salt, str) else salt
    hash_bytes = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, 100_000)
    return base64.b64encode(hash_bytes).decode('utf-8')

def generate_hashed_password(password):
    salt = secrets.token_bytes(16)  # 128-bit salt
    salt_b64 = base64.b64encode(salt).decode('utf-8')
    hashed_password = get_hashed_password(password, salt)
    return hashed_password, salt_b64

def get_user_info(data):
    username = data.get('username')
    if not username:
        return Message.failure('Username is required').to_dict()

    user_info_response, error = get_request(routes['get_user_info'], {'username': username})
    if error:
        return error
    
    return user_info_response
    

def get_game_server(data):
    # load_balancer.get_server()
    # response = post_request(routes['assign_user'], {'username': username, 'server_id': server})
    return Message.success(redirect='http://localhost:4999').to_dict()
    