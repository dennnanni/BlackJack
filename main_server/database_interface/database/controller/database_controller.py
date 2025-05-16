from http import HTTPStatus
from flask import Blueprint, jsonify, request
from database.model.database_actions import add_user, get_user
from main_server.common.structures import UserDatabase, Message, UserLogin

database_bp = Blueprint('database', __name__)

@database_bp.route('/register', methods=['POST'])
def register_user_route():
    data = request.get_json()
    user = UserDatabase(**data)
    result = add_user(user.username, user.password, user.salt, user.balance)
    if result is True:
        return jsonify(Message.success('User added successfully').to_dict()), HTTPStatus.CREATED
    else:
        print(f'Error adding user: {result}')
        return jsonify(Message.failure(f'Error adding user: {result}').to_dict()), HTTPStatus.BAD_REQUEST

@database_bp.route('/get_salt', methods=['POST'])
def get_salt_route():
    data = request.get_json()
    username = data
    if not username:
        return jsonify(Message.failure('Username is required').to_dict()), HTTPStatus.BAD_REQUEST
    
    user = get_user(username)
    if user:
        return jsonify({'salt': user.salt}), HTTPStatus.OK
    else:
        return jsonify(Message.failure('User not found').to_dict()), HTTPStatus.NOT_FOUND
    
@database_bp.route('/login', methods=['POST'])
def login_user_route():
    data = request.get_json()
    user = UserLogin(**data)
    user_db = get_user(user.username)
    if user.password == user_db.password:
        return jsonify(Message.success('User logged in successfully').to_dict()), HTTPStatus.OK
    else:
        print(f'Wrong password for user: {user.username}')
        return jsonify(Message.failure(f'Wrong password').to_dict()), HTTPStatus.BAD_REQUEST