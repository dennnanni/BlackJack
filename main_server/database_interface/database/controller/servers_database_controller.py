from dataclasses import asdict
from http import HTTPStatus
import json
from common.structures import Message, Server
from flask import Blueprint, jsonify


servers_routes_bp = Blueprint('servers_db', __name__)

@servers_routes_bp.route('/active', methods=['GET'])
def get_active_servers_route():
    """
    Route to get the list of active servers.
    """
    # This is a placeholder for the actual implementation which would query the database
    active_servers = [
        Server(
            id=1,
            ip='127.0.0.1',
            port=4999,
            connected_users=10, 
            max_users=9
        ),
        Server(
            id=1,
            ip='127.0.0.1',
            port=4998,
            connected_users=10, 
            max_users=9
        ),
    ]
    
    return jsonify(Message.success(data=[asdict(server) for server in active_servers]).to_dict()), HTTPStatus.OK