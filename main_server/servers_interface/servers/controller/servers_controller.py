from http import HTTPStatus
import json
from common.http_requests import get_request, post_request
from common.response_fields import ENCRYPTED, ERROR, SUCCESS, TOKEN
from common.structures import Server
from flask import Blueprint, jsonify, request
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from servers import DATABASE_URL, fernet_shared_secret
from servers.constants import GET_SERVER_KEY_API_ENDPOINT, PUBLISH_RESULT_API_ENDPOINT, REGISTER_NEW_SERVER_API_ENDPOINT
from cryptography.fernet import Fernet

servers_bp = Blueprint('servers', __name__)

@servers_bp.route('/register', methods=['POST'])
def index():
    data = request.get_data()
    if not data:
        return jsonify({ERROR: 'No data provided'}), HTTPStatus.BAD_REQUEST
    
    # decrypt the message with the shared secret
    cleartext = fernet_shared_secret.decrypt(data).decode()
    
    print(f'Decrypted data: {cleartext}')
    
    try:
        dict = json.loads(cleartext)
        # parse the message
        server = Server(**dict)
    except Exception as e:
        return jsonify({ERROR: f'Error in parsing data {e}'}), HTTPStatus.BAD_REQUEST
    
    fernet_private = Fernet(server.key.encode())
    server.key = fernet_shared_secret.encrypt(server.key.encode()).decode()
    
    # register the server in the database
    result = post_request(DATABASE_URL, REGISTER_NEW_SERVER_API_ENDPOINT, server.to_dict())
    if result.get(ERROR):
        return result
    
    encrypted_data = fernet_private.encrypt(cleartext.encode()).decode()
    
    # success message contains data sent from the server encrypted with its key for validity
    return jsonify({ENCRYPTED: encrypted_data}), HTTPStatus.CREATED

@servers_bp.route('/result', methods=['POST'])
def publish_results_route():
    data = request.get_json()
    if not data or TOKEN not in data:
        return jsonify({ERROR: 'Missing token in result post'}), HTTPStatus.BAD_REQUEST

    token = data.get(TOKEN)
    server_id = request.headers.get("X-Server-ID")
    if not server_id or not server_id.isdigit():
        return jsonify({ERROR: 'Missing server ID'}), HTTPStatus.UNAUTHORIZED
    
    # Recupera la chiave del game_server
    key_response = get_request(DATABASE_URL, GET_SERVER_KEY_API_ENDPOINT, params={'id': int(server_id)})
    if ENCRYPTED not in key_response:
        return jsonify({ERROR: 'Invalid server ID'}), HTTPStatus.UNAUTHORIZED

    try:
        secret = fernet_shared_secret.decrypt(key_response.get(ENCRYPTED).encode()).decode()
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except ExpiredSignatureError:
        return jsonify({ERROR: 'Token expired'}), HTTPStatus.UNAUTHORIZED
    except InvalidTokenError as e:
        return jsonify({ERROR: f'Invalid token {str(e)}'}), HTTPStatus.UNAUTHORIZED
    except Exception as e:
        return jsonify({ERROR: f'Bad data in token: {str(e)}'}), HTTPStatus.BAD_REQUEST
        
    response = post_request(DATABASE_URL, PUBLISH_RESULT_API_ENDPOINT, json_data=payload.get('results'))
    if response.get(ERROR):
        return jsonify(response), HTTPStatus.INTERNAL_SERVER_ERROR

    # Qui puoi salvare i risultati nel database
    return jsonify({SUCCESS: True}), HTTPStatus.OK