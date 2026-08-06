"""HTTP API the game servers call. Every endpoint is authorized by a Bearer
JWT signed with the SHARED_SECRET (see central_server.auth).
"""
from http import HTTPStatus

from flask import Blueprint, jsonify, request

from central_server import auth, db
from shared.messages import (CAPACITY, ERROR, HOST, LOAD, PORT, RESULTS,
                             ROUND_ID, SERVER_ID, SUCCESS, Result)

api_bp = Blueprint('api', __name__, url_prefix='/api/servers')


def _unauthorized():
    return jsonify({ERROR: 'Missing or invalid server token'}), HTTPStatus.UNAUTHORIZED


def _token_payload():
    """Claims of the request's Bearer token, or None if it is missing,
    invalid or expired."""
    return auth.verify_server_token(request.headers.get('Authorization'))


def _server_id():
    """The server_id claim of the request's Bearer token, or None if the
    token is unusable or carries no id yet."""
    payload = _token_payload()
    return payload.get(SERVER_ID) if payload else None


@api_bp.route('/register', methods=['POST'])
def register():
    # Bootstrap call: the token proves knowledge of SHARED_SECRET but carries
    # no server_id yet; central assigns one here.
    if _token_payload() is None:
        return _unauthorized()

    data = request.get_json(silent=True) or {}
    host, port, capacity = data.get(HOST), data.get(PORT), data.get(CAPACITY)
    if not host or not isinstance(port, int) or not isinstance(capacity, int) or capacity <= 0:
        return jsonify({ERROR: 'host, port and capacity are required'}), HTTPStatus.BAD_REQUEST

    server_id = db.register_server(host, port, capacity)
    return jsonify({SERVER_ID: server_id}), HTTPStatus.CREATED


@api_bp.route('/heartbeat', methods=['POST'])
def heartbeat():
    server_id = _server_id()
    if server_id is None:
        return _unauthorized()

    data = request.get_json(silent=True) or {}
    load = data.get(LOAD)
    if not isinstance(load, int) or load < 0:
        return jsonify({ERROR: 'load is required'}), HTTPStatus.BAD_REQUEST

    if not db.heartbeat(server_id, load):
        # Unknown id (e.g. the registry was reset): the server should re-register.
        return jsonify({ERROR: 'Unknown server id'}), HTTPStatus.NOT_FOUND
    return jsonify({SUCCESS: True}), HTTPStatus.OK


@api_bp.route('/results', methods=['POST'])
def results():
    if _server_id() is None:
        return _unauthorized()

    data = request.get_json(silent=True) or {}
    round_id = data.get(ROUND_ID)
    if not round_id or not isinstance(round_id, str):
        return jsonify({ERROR: 'round_id is required'}), HTTPStatus.BAD_REQUEST
    try:
        round_results = [Result.from_dict(r) for r in data[RESULTS]]
    except (KeyError, TypeError, ValueError):
        return jsonify({ERROR: 'Malformed results payload'}), HTTPStatus.BAD_REQUEST

    # Idempotent: replaying the same round_id returns without re-applying, so
    # at-least-once delivery from the outbox becomes exactly-once effect.
    db.apply_results(round_id, round_results)
    return jsonify({SUCCESS: True}), HTTPStatus.OK
