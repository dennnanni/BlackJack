from http import HTTPStatus
from common.response_fields import DATA, ERROR, SUCCESS
from common.structures import RegisteredServer
from database.model.database_actions import get_servers_with_user_count, register_server
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