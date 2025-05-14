from http import HTTPStatus
from flask import Blueprint, jsonify, request
from database.model.database_actions import add_user
from main_server.common.structures import User, Message

database_bp = Blueprint('database', __name__)

@database_bp.route('/add_user', methods=['POST'])
def add_user_route():
    data = request.get_json()
    user = User(**data)
    result = add_user(user.username, user.password, user.salt, user.balance)
    if result is True:
        return jsonify(Message(True, 'User added successfully').to_dict()), HTTPStatus.CREATED
    else:
        return jsonify(Message(False, f'Error adding user').to_dict()), HTTPStatus.BAD_REQUEST