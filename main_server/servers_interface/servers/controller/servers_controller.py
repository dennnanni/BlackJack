from http import HTTPStatus
import json
from common.http_requests import post_request
from common.response_fields import ENCRYPTED, ERROR
from common.structures import Server
from flask import Blueprint, jsonify, request
from servers import DATABASE_URL, fernet_shared_secret
from servers.constants import REGISTER_NEW_SERVER_API_ENDPOINT
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
    return jsonify({ENCRYPTED: encrypted_data}), HTTPStatus.OK