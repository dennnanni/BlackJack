from dataclasses import asdict
from http import HTTPStatus
import json
from common.structures import Message, Server
from database.model.database_actions import get_servers_with_user_count
from flask import Blueprint, jsonify


servers_routes_bp = Blueprint('servers_db', __name__)

@servers_routes_bp.route('/load', methods=['GET'])
def get_active_servers_route():
    """
    Route to get the list of servers with related connected user count.
    """
    servers = get_servers_with_user_count()
    
    if servers is None:
        return jsonify(Message.failure('Error retrieving active servers').to_dict()), HTTPStatus.INTERNAL_SERVER_ERROR
    
    servers = [Server.from_tuple(server) for server in servers]
        
    return jsonify(Message.success(data=[server.to_dict() for server in servers]).to_dict()), HTTPStatus.OK