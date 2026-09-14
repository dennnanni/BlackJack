"""HTTP API the game servers call."""
from http import HTTPStatus
from central_server import db
from central_server import auth
from shared.messages import CAPACITY, ERROR, SERVER_ID, SUCCESS, RESULTS, HOST, PORT, Result
from flask import Blueprint, jsonify, request

api_bp = Blueprint('api', __name__, url_prefix='/api/servers')


@api_bp.route('/register', methods=['POST'])
def register():
    if auth.verify_server_token(request.headers.get('Authorization')) is None:
        return jsonify({ERROR: 'Missing or invalid server token'}), HTTPStatus.UNAUTHORIZED

    data = request.get_json(silent=True) or {}
    host, port, capacity = data.get(HOST), data.get(PORT), data.get(CAPACITY)
    if not host or not port or not capacity:
        return jsonify({ERROR: 'host and port are required'}), HTTPStatus.BAD_REQUEST
    
    server_id = db.register_server(host, port, capacity)
    return jsonify({SERVER_ID: server_id}), HTTPStatus.CREATED

@api_bp.route('/results', methods=['POST'])
def results():
    if auth.verify_server_token(request.headers.get('Authorization')) is None:
        return jsonify({ERROR: 'Missing or invalid server token'}), HTTPStatus.UNAUTHORIZED

    data = request.get_json(silent=True) or {}
    try:
        results = [Result.from_dict(r) for r in data[RESULTS]]
    except:
        return jsonify({ERROR: 'Malformed results payload'}), HTTPStatus.BAD_REQUEST

    db.update_users_balance(results)
    return jsonify({SUCCESS: True}), HTTPStatus.OK