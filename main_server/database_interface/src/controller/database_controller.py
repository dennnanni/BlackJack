from flask import Blueprint, jsonify, request
from src.model.database_actions import add_user
from src.model.db_model import User

database_bp = Blueprint('database', __name__)

@database_bp.route('add_user', methods=['POST'])
def add_user_controller():
    data = request.get_json()
    user = User(**data)
    result = add_user(**user)
    if result is True:
        return jsonify("User added")
    else:
        return jsonify(result, status=400)