from flask import Blueprint, render_template, request, jsonify, g
import jwt
from src.config.settings import SHARED_SECRET
game_bp = Blueprint('game', __name__)

@game_bp.route('/')
def index():
    return render_template('index.html', title='Game Server')

@game_bp.route('/join', methods=['POST'])
def join():
    data = request.json
    token = data.get('token')
    if not token:
        return jsonify({"error": "Token mancante"}), 400
    
    try:
        payload = jwt.decode(token, SHARED_SECRET, algorithms=['HS256'])
        g.user = payload
    except jwt.InvalidTokenError:
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    return jsonify({"status": "ok", "username": payload["username"]}), 200
