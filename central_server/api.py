"""HTTP API the game servers call. Every endpoint is authorized by a Bearer
JWT signed with the SHARED_SECRET (see central_server.auth).
"""
from http import HTTPStatus

from flask import Blueprint, jsonify, request

from central_server import auth, db
from shared.messages import CAPACITY, ERROR, HOST, LOAD, PORT, RESULTS, SERVER_ID, SUCCESS, Result

api_bp = Blueprint('api', __name__, url_prefix='/api/servers')


def _authorized(require_server_id=False):
    """Verify the Bearer server token; returns (payload, error_response)."""
    payload = auth.verify_server_token(request.headers.get('Authorization'))
    if payload is None:
        return None, (jsonify({ERROR: 'Missing or invalid server token'}), HTTPStatus.UNAUTHORIZED)
    if require_server_id and SERVER_ID not in payload:
        return None, (jsonify({ERROR: 'Token has no server_id claim'}), HTTPStatus.UNAUTHORIZED)
    return payload, None


@api_bp.route('/register', methods=['POST'])
def register():
    # Bootstrap call: the token proves knowledge of SHARED_SECRET but carries
    # no server_id yet; central assigns one here.
    _, error = _authorized()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    host, port, capacity = data.get(HOST), data.get(PORT), data.get(CAPACITY)
    if not host or not isinstance(port, int) or not isinstance(capacity, int) or capacity <= 0:
        return jsonify({ERROR: 'host, port and capacity are required'}), HTTPStatus.BAD_REQUEST

    server_id = db.register_server(host, port, capacity)
    if server_id is None:
        return jsonify({ERROR: 'Failed to register the server'}), HTTPStatus.INTERNAL_SERVER_ERROR
    return jsonify({SERVER_ID: server_id}), HTTPStatus.CREATED


@api_bp.route('/heartbeat', methods=['POST'])
def heartbeat():
    payload, error = _authorized(require_server_id=True)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    load = data.get(LOAD)
    if not isinstance(load, int) or load < 0:
        return jsonify({ERROR: 'load is required'}), HTTPStatus.BAD_REQUEST

    if not db.heartbeat(payload[SERVER_ID], load):
        # Unknown id (e.g. the registry was reset): the server should re-register.
        return jsonify({ERROR: 'Unknown server id'}), HTTPStatus.NOT_FOUND
    return jsonify({SUCCESS: True}), HTTPStatus.OK


@api_bp.route('/results', methods=['POST'])
def results():
    payload, error = _authorized(require_server_id=True)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    try:
        round_results = [Result.from_dict(r) for r in data[RESULTS]]
    except (KeyError, TypeError, ValueError):
        return jsonify({ERROR: 'Malformed results payload'}), HTTPStatus.BAD_REQUEST

    if not db.update_users_balance(round_results):
        return jsonify({ERROR: 'Failed to persist results'}), HTTPStatus.INTERNAL_SERVER_ERROR
    return jsonify({SUCCESS: True}), HTTPStatus.OK
