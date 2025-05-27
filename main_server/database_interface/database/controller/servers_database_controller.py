from http import HTTPStatus
from common.response_fields import DATA, ENCRYPTED, ERROR, SUCCESS
from common.structures import RegisteredServer, Result
from database.model.database_actions import get_server_key, get_servers_with_user_count, register_server, update_users_balance
from database.orm.orm import GameServer
from flask import Blueprint, jsonify, request


servers_routes_bp = Blueprint('servers_db', __name__)

@servers_routes_bp.route('/load', methods=['GET'])
def get_active_servers_route():
    """
    Route to get the list of servers with related connected user count.
    """
    servers = get_servers_with_user_count()
    
    if servers is None:
        return jsonify({ERROR: 'Error in retrieving servers\'loads'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    servers = [RegisteredServer.from_tuple(server) for server in servers]
        
    return jsonify({DATA: [server.to_dict() for server in servers]}), HTTPStatus.OK

@servers_routes_bp.route('/register', methods=['POST'])
def register_server_route():
    """
    Route to register a new server.
    """
    data = request.get_json()
    
    if not data:
        return jsonify({ERROR: 'No data provided'}), HTTPStatus.BAD_REQUEST
    
    try:
        server = GameServer(**data)
    except Exception as e:
        print(f'Error parsing server data: {e}')
        return jsonify({ERROR: f'Invalid data {data}'}), HTTPStatus.BAD_REQUEST
    
    if not register_server(server):
        return jsonify({ERROR: 'Failed to register the server'}), HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify({SUCCESS: True}), HTTPStatus.CREATED

@servers_routes_bp.route('/key', methods=['GET'])
def get_server_key_route():
    server_id = request.args.get('id')
    if not server_id or not server_id.isdigit():
        return jsonify({ERROR: 'Invalid server ID'}), HTTPStatus.BAD_REQUEST
    
    key = get_server_key(int(server_id))
    if not key:
        return jsonify({ERROR: 'Server not found'}), HTTPStatus.NOT_FOUND
    return jsonify({ENCRYPTED: key}), HTTPStatus.OK

@servers_routes_bp.route('/results', methods=['POST'])
def publish_results_route():
    """
    Route to publish results from a server.
    """
    data = request.get_json()
    
    print(f'Received data: {data}')
    
    results = []
    for result in data:
        results.append(Result(**result))
        
    result = update_users_balance(results)
    if isinstance(result, str):
        return jsonify({ERROR: result}), HTTPStatus.BAD_REQUEST
    
    return jsonify({SUCCESS: True}), HTTPStatus.OK