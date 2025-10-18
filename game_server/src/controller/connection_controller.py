from flask import Blueprint, render_template, request, jsonify, g
import jwt
from src import key
game_bp = Blueprint('game', __name__)

@game_bp.route('/')
def index():
    return render_template('index.html', title='Game Server')

@game_bp.route('/join', methods=['POST'])
def join():
    token = request.form.get('token')
    if not token:
        return jsonify({'error': 'Token is required'}), 400
    try:
        payload = jwt.decode(token, key, algorithms=['HS256'])
        g.user = payload
    except jwt.InvalidTokenError as error:
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    return jsonify({'status': 'ok', 'username': payload['username']}), 200
