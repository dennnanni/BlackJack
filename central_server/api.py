"""HTTP API the game servers call."""
from http import HTTPStatus
import json
from central_server import db
from central_server.auth import fernet_shared_secret
from shared.messages import ENCRYPTED, ERROR, SERVER_ID, SUCCESS, TOKEN, Result, Server
from flask import Blueprint, jsonify, request
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from cryptography.fernet import Fernet

api_bp = Blueprint('api', __name__, url_prefix='/api/servers')


@api_bp.route('/register', methods=['POST'])
def index():
    data = request.get_json(silent=True)
    if not data or ENCRYPTED not in data:
        return jsonify({ERROR: 'No data provided'}), HTTPStatus.BAD_REQUEST

    try:
        encrypted_payload = data[ENCRYPTED].encode()  # encoded base64 string
        # decrypt the message with the shared secret
        cleartext = fernet_shared_secret.decrypt(encrypted_payload).decode()
    except Exception as e:
        return jsonify({ERROR: f'Invalid encrypted data: {e}'}), HTTPStatus.BAD_REQUEST

    try:
        dict = json.loads(cleartext)
        # parse the message
        server = Server(**dict)
    except Exception as e:
        return jsonify({ERROR: f'Error in parsing data {e}'}), HTTPStatus.BAD_REQUEST

    fernet_private = Fernet(server.key.encode())
    server.key = fernet_shared_secret.encrypt(server.key.encode()).decode()

    server_id = db.register_server(db.GameServer(**server.to_dict()))
    if not server_id:
        return jsonify({ERROR: 'Failed to register the server'}), HTTPStatus.INTERNAL_SERVER_ERROR

    response_payload = {
        **json.loads(cleartext),
        SERVER_ID: server_id
    }
    encrypted_data = fernet_private.encrypt(json.dumps(response_payload).encode()).decode()

    # success message contains data sent from the server encrypted with its key for validity
    return jsonify({ENCRYPTED: encrypted_data}), HTTPStatus.CREATED

@api_bp.route('/results', methods=['POST'])
def publish_results_route():
    data = request.get_json()
    if not data or TOKEN not in data:
        return jsonify({ERROR: 'Missing token in result post'}), HTTPStatus.BAD_REQUEST

    token = data.get(TOKEN)
    server_id = request.headers.get("X-Server-ID")
    if not server_id or not server_id.isdigit():
        return jsonify({ERROR: 'Missing server ID'}), HTTPStatus.UNAUTHORIZED

    key = db.get_server_key(int(server_id))
    if not key:
        return jsonify({ERROR: 'Invalid server ID'}), HTTPStatus.UNAUTHORIZED

    try:
        secret = fernet_shared_secret.decrypt(key.encode()).decode()
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except ExpiredSignatureError:
        return jsonify({ERROR: 'Token expired'}), HTTPStatus.UNAUTHORIZED
    except InvalidTokenError as e:
        return jsonify({ERROR: f'Invalid token {str(e)}'}), HTTPStatus.UNAUTHORIZED
    except Exception as e:
        return jsonify({ERROR: f'Bad data in token: {str(e)}'}), HTTPStatus.BAD_REQUEST

    results = [Result(**result) for result in payload.get('results')]
    if db.update_users_balance(results) is not True:
        return jsonify({ERROR: 'Failed to update balances'}), HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify({SUCCESS: True}), HTTPStatus.OK
