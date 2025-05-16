import base64
import hashlib
import secrets
import requests
from main_server.common.structures import RedirectionMessage, UserLogin, UserDatabase, Message

database_url = 'http://localhost:5001'

def validate_user_input(data):
    try:
        user = UserLogin(**data)
        if not user.is_valid:
            return None, Message.failure('Wrong or missing data').to_dict()
        return user, None
    except TypeError as e:
        return None, Message.failure(f'Wrong or missing data: {e}').to_dict()

def post_request(endpoint, json_data):
    try:
        response = requests.post(f'{database_url}/{endpoint}', json=json_data)
        response.raise_for_status()
        return response.json(), None
    except requests.HTTPError as e:
        print(f'HTTP error: {e.response}')
        return None, Message.failure('HTTP error').to_dict()
    except requests.RequestException as e:
        print(f'Request exception: {e}')
        return None, Message.failure('Something went wrong while contacting the server').to_dict()
    except ValueError:
        return None, Message.failure('Server response is not valid').to_dict()

def login_user(data):
    user, error = validate_user_input(data)
    if error:
        return error

    salt_response, error = post_request('get_salt', user.username)
    if error:
        return error

    salt = salt_response.get('salt')
    if not salt:
        print('No salt found in response')
        return salt_response  # Could contain error message from server

    hashed_password = get_hashed_password(user.password, salt)
    login_data = UserLogin(username=user.username, password=hashed_password).to_dict()

    login_response, error = post_request('login', login_data)
    if error:
        return error

    message = Message(**login_response)
    if message.success:
        return RedirectionMessage.success('Login successful!', f'/user/{user.username}').to_dict()
    return message.to_dict()

def register_user(data):
    user, error = validate_user_input(data)
    if error:
        return error

    hashed_password, salt = generate_hashed_password(user.password)
    user_db = UserDatabase(username=user.username, password=hashed_password, salt=salt, balance=0.0)

    register_response, error = post_request('register', user_db.to_dict())
    if error:
        return error

    message = Message(**register_response)
    if message.success:
        return RedirectionMessage.success('Registration successful!', f'/{user.username}').to_dict()
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
