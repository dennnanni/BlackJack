"""HTTP API the game servers call."""
from http import HTTPStatus
from central_server import db
from central_server import auth
from shared.messages import BUY_INS, CAPACITY, ERROR, ROUND_ID, SERVER_ID, SUCCESS, RESULTS, HOST, PORT, PLAYERS, Result
from flask import Blueprint, jsonify, request

api_bp = Blueprint('api', __name__, url_prefix='/api/servers')


@api_bp.route('/register', methods=['POST'])
def register():
    if auth.verify_server_token(request.headers.get('Authorization')) is None:
        return jsonify({ERROR: 'Missing or invalid server token'}), HTTPStatus.UNAUTHORIZED

    data = request.get_json(silent=True) or {}
    host, port, capacity = data.get(HOST), data.get(PORT), data.get(CAPACITY)
    if not host or not port or not capacity:
        return jsonify({ERROR: 'host and port are required'}), HTTPStatus.BAD_REQUEST
    
    server_id = db.register_server(host, port, capacity)
    return jsonify({SERVER_ID: server_id}), HTTPStatus.CREATED

@api_bp.route('/results', methods=['POST'])
def results():
    payload = auth.verify_server_token(request.headers.get('Authorization'))
    if payload is None:
        return jsonify({ERROR: 'Missing or invalid server token'}), HTTPStatus.UNAUTHORIZED

    server_id = payload.get(SERVER_ID)
    data = request.get_json(silent=True) or {}
    round_id = data.get(ROUND_ID)
    if not round_id:
        return jsonify({ERROR: 'round_id is required'}), HTTPStatus.BAD_REQUEST
    try:
        results = [Result.from_dict(r) for r in data[RESULTS]]
    except:
        return jsonify({ERROR: 'Malformed results payload'}), HTTPStatus.BAD_REQUEST

    db.apply_round(round_id, server_id, results)
    return jsonify({SUCCESS: True}), HTTPStatus.OK

@api_bp.route('/leave', methods=['POST'])
def leave():
    payload = auth.verify_server_token(request.headers.get('Authorization'))
    if payload is None:
        return jsonify({ERROR: 'Missing or invalid server token'}), HTTPStatus.UNAUTHORIZED

    server_id = payload.get(SERVER_ID)
    data = request.get_json(silent=True) or {}
    buy_ins = data.get(BUY_INS)
    if not isinstance(buy_ins, list):
        return jsonify({ERROR: 'buy_ins is required'}), HTTPStatus.BAD_REQUEST

    db.close_buy_in(server_id, buy_ins)
    return jsonify({SUCCESS: True}), HTTPStatus.OK

@api_bp.route('/heartbeat', methods=['POST'])
def heartbeat():
    payload = auth.verify_server_token(request.headers.get('Authorization'))
    if payload is None:
        return jsonify({ERROR: 'Missing or invalid server token'}), HTTPStatus.UNAUTHORIZED

    server_id = payload.get(SERVER_ID) if payload else None
    data = request.get_json(silent=True) or {}
    players = data.get(PLAYERS)
    if not isinstance(players, list):
        return jsonify({ERROR: 'players is required'}), HTTPStatus.BAD_REQUEST

    if not db.update_heartbeat(server_id, players):
        return jsonify({ERROR: 'Unknown server id'}), HTTPStatus.NOT_FOUND
    return jsonify({SUCCESS: True}), HTTPStatus.OK
