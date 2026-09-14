import time

import jwt
import pytest

from central_server import db
from shared.messages import Result

USERNAME = 'user'
ROUND_1 = 'round-1'
ROUND_2 = 'round-2'


def _balance(session_db, username):
    return float(session_db.get_user(username).balance)


@pytest.fixture
def sample_user(session_db):
    session_db.add_user(USERNAME, 'hash', 'salt', 1000)
    return USERNAME


def test_same_round_applies_once(session_db, sample_user):
    results = [Result(USERNAME, -100.0)]

    db.apply_round(ROUND_1, results)
    assert _balance(session_db, sample_user) == 900.0

    db.apply_round(ROUND_1, results)
    assert _balance(session_db, sample_user) == 900.0


def test_different_rounds_both_apply(session_db, sample_user):
    db.apply_round(ROUND_1, [Result(USERNAME, -100.0)])
    db.apply_round(ROUND_2, [Result(USERNAME, 50.0)])
    assert _balance(session_db, sample_user) == 950.0


def test_results_endpoint_applies_once(session_db, sample_user):
    from central_server.app import create_app
    app = create_app()
    client = app.test_client()

    now = int(time.time())
    bearer = jwt.encode({'server_id': 1, 'iat': now, 'exp': now + 60},
                        'test-secret', algorithm='HS256')
    payload = {'round_id': 'round-http',
               'results': [{'username': USERNAME, 'balance_difference': -250.0}]}

    for _ in range(2):  # second delivery is a retry, should not be applied but should receive an ACK
        response = client.post('/api/servers/results', json=payload,
                               headers={'Authorization': f'Bearer {bearer}'})
        assert response.status_code == 200

    assert _balance(session_db, sample_user) == 750.0


def test_results_endpoint_rejects_bad_tokens(session_db, sample_user):
    from central_server.app import create_app
    app = create_app()
    client = app.test_client()

    payload = {'round_id': 'round-x',
               'results': [{'username': USERNAME, 'balance_difference': 250.0}]}

    response = client.post('/api/servers/results', json=payload)
    assert response.status_code == 401

    now = int(time.time())
    forged = jwt.encode({'server_id': 1, 'iat': now, 'exp': now + 60},
                        'wrong-secret', algorithm='HS256')
    response = client.post('/api/servers/results', json=payload,
                           headers={'Authorization': f'Bearer {forged}'})
    assert response.status_code == 401

    assert _balance(session_db, sample_user) == 1000.0
