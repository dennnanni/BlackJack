from http import HTTPStatus
from common.response_fields import DATA, ERROR, SALT, SUCCESS, PLAYING
from flask import Blueprint, jsonify, request
from database.model.database_actions import add_user, get_user, is_user_playing
from common.structures import UserDatabase, UserInfo, UserLogin

users_routes_bp = Blueprint('users_db', __name__)

@users_routes_bp.route('/register', methods=['POST'])
def register_user_route():
    data = request.get_json()
    user = UserDatabase(**data)
    result = add_user(user.username, user.password, user.salt, user.balance)
    if result is True:
        return jsonify({SUCCESS: True}), HTTPStatus.CREATED
    else:
        print(f'Error adding user: {result}')
        return jsonify({ERROR: f'Error adding user {user.username}'}), HTTPStatus.BAD_REQUEST

@users_routes_bp.route('/salt', methods=['GET'])
def get_salt_route():
    username = request.args.get('username')
    if not username:
        return jsonify({ERROR: 'Username is required to get salt'}), HTTPStatus.BAD_REQUEST
    
    user = get_user(username)
    if user:
        return jsonify({SALT: user.salt}), HTTPStatus.OK
    else:
        return jsonify({ERROR: f'User {username} not found'}), HTTPStatus.NOT_FOUND
    
@users_routes_bp.route('/login', methods=['POST'])
def login_user_route():
    data = request.get_json()
    user = UserLogin(**data)
    user_db = get_user(user.username)
    # TODO check if user is in db
    if user.password == user_db.password:
        return jsonify({SUCCESS: True}), HTTPStatus.OK
    else:
        print(f'Wrong password for user: {user.username}')
        return jsonify({ERROR: f'Wrong password for user {user.username}'}), HTTPStatus.BAD_REQUEST
    
@users_routes_bp.route('/info', methods=['GET'])
def get_user_info_route():
    username = request.args.get('username')
    if not username:
        return jsonify({ERROR: 'Username is required to get info'}), HTTPStatus.BAD_REQUEST
    
    user = get_user(username)
    if user:
        return jsonify({DATA: UserInfo(user.username, user.balance).to_dict()}), HTTPStatus.OK
    else:
        return jsonify({ERROR: f'User {user.username} not found'}), HTTPStatus.NOT_FOUND
    
@users_routes_bp.route('/playing', methods=['GET'])
def user_playing_route():
    username = request.args.get('username')
    if not username:
        return jsonify({ERROR: 'Username is required to get player status'}), HTTPStatus.BAD_REQUEST
    
    playing = is_user_playing(username)
    return jsonify({PLAYING: playing}), HTTPStatus.OK