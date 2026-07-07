"""At-least-once delivery + idempotent application = exactly-once effect:
replaying a round_id must ACK without moving any balance again.
"""
import time

import jwt
import pytest

from central_server import db
from shared.messages import Result


def _balance(session_db, username):
    return float(session_db.get_user(username).balance)


@pytest.fixture
def alice(session_db):
    session_db.add_user('alice', 'hash', 'salt', 1000)
    return 'alice'


def test_same_round_applies_once(session_db, alice):
    results = [Result('alice', -100.0)]

    assert db.apply_results('round-1', results) is True
    assert _balance(session_db, alice) == 900.0

    # duplicate delivery (retry after a partition heal): ACK, no re-apply
    assert db.apply_results('round-1', results) is True
    assert _balance(session_db, alice) == 900.0


def test_different_rounds_both_apply(session_db, alice):
    assert db.apply_results('round-1', [Result('alice', -100.0)]) is True
    assert db.apply_results('round-2', [Result('alice', 50.0)]) is True
    assert _balance(session_db, alice) == 950.0


def test_results_endpoint_is_idempotent(session_db, alice):
    from central_server.app import create_app
    app = create_app()
    client = app.test_client()

    now = int(time.time())
    bearer = jwt.encode({'server_id': 1, 'iat': now, 'exp': now + 60},
                        'test-secret', algorithm='HS256')
    payload = {'round_id': 'round-http',
               'results': [{'username': 'alice', 'balance_difference': -250.0}]}

    for _ in range(2):  # second delivery is a retry: same ACK, single effect
        response = client.post('/api/servers/results', json=payload,
                               headers={'Authorization': f'Bearer {bearer}'})
        assert response.status_code == 200

    assert _balance(session_db, alice) == 750.0


def test_results_endpoint_rejects_bad_tokens(session_db, alice):
    from central_server.app import create_app
    app = create_app()
    client = app.test_client()

    payload = {'round_id': 'round-x',
               'results': [{'username': 'alice', 'balance_difference': -250.0}]}

    response = client.post('/api/servers/results', json=payload)
    assert response.status_code == 401

    now = int(time.time())
    forged = jwt.encode({'server_id': 1, 'iat': now, 'exp': now + 60},
                        'wrong-secret', algorithm='HS256')
    response = client.post('/api/servers/results', json=payload,
                           headers={'Authorization': f'Bearer {forged}'})
    assert response.status_code == 401

    assert _balance(session_db, alice) == 1000.0
