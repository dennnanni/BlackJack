import time

import jwt
import pytest

from central_server import db
from shared.messages import Result

USERNAME = 'user'
ROUND_1 = 'round-1'
ROUND_2 = 'round-2'


def _remaining(session_db, buy_in_id):
    with session_db.SessionLocal() as session:
        return float(session.get(session_db.BuyIn, buy_in_id).remaining)


def _bearer(server_id, secret='test-secret', typ='server'):
    now = int(time.time())
    claims = {'server_id': server_id, 'iat': now, 'exp': now + 60}
    if typ is not None:
        claims['typ'] = typ
    return jwt.encode(claims, secret, algorithm='HS256')


@pytest.fixture
def buy_in(session_db):
    """A player seated on a server with their whole 1000 balance."""
    session_db.add_user(USERNAME, 'hash', 'salt', 1000)
    server_id = session_db.register_server('localhost', 8000, 10)
    buy_in_id, _ = session_db.create_buy_in(USERNAME, server_id, 1000)
    return server_id, buy_in_id


def test_same_round_applies_once(session_db, buy_in):
    server_id, buy_in_id = buy_in
    results = [Result(USERNAME, buy_in_id, -100.0)]

    db.apply_round(ROUND_1, server_id, results)
    assert _remaining(session_db, buy_in_id) == 900.0

    db.apply_round(ROUND_1, server_id, results)
    assert _remaining(session_db, buy_in_id) == 900.0


def test_different_rounds_both_apply(session_db, buy_in):
    server_id, buy_in_id = buy_in
    db.apply_round(ROUND_1, server_id, [Result(USERNAME, buy_in_id, -100.0)])
    db.apply_round(ROUND_2, server_id, [Result(USERNAME, buy_in_id, 50.0)])
    assert _remaining(session_db, buy_in_id) == 950.0


def test_results_endpoint_applies_once(session_db, buy_in):
    from central_server.app import create_app
    client = create_app().test_client()
    server_id, buy_in_id = buy_in

    payload = {'round_id': 'round-http',
               'results': [{'username': USERNAME, 'buy_in_id': buy_in_id,
                            'balance_difference': -250.0}]}

    for _ in range(2):  # second delivery is a retry, should not be applied but should receive an ACK
        response = client.post('/api/servers/results', json=payload,
                               headers={'Authorization': f'Bearer {_bearer(server_id)}'})
        assert response.status_code == 200

    assert _remaining(session_db, buy_in_id) == 750.0


def test_results_endpoint_rejects_bad_tokens(session_db, buy_in):
    from central_server.app import create_app
    client = create_app().test_client()
    server_id, buy_in_id = buy_in

    payload = {'round_id': 'round-x',
               'results': [{'username': USERNAME, 'buy_in_id': buy_in_id,
                            'balance_difference': 250.0}]}

    response = client.post('/api/servers/results', json=payload)
    assert response.status_code == 401

    forged = _bearer(server_id, secret='wrong-secret')
    response = client.post('/api/servers/results', json=payload,
                           headers={'Authorization': f'Bearer {forged}'})
    assert response.status_code == 401

    # a token signed with the right secret but no typ
    untyped = _bearer(server_id, typ=None)
    response = client.post('/api/servers/results', json=payload,
                           headers={'Authorization': f'Bearer {untyped}'})
    assert response.status_code == 401

    assert _remaining(session_db, buy_in_id) == 1000.0


def test_players_join_token_cannot_post_results(session_db, buy_in):
    from central_server import auth
    from central_server.app import create_app
    client = create_app().test_client()
    server_id, buy_in_id = buy_in

    join_token = auth.create_join_token(USERNAME, server_id, buy_in_id, 1000)
    response = client.post(
        '/api/servers/results',
        json={'round_id': 'stolen', 'results': [{'username': USERNAME,
                                                 'buy_in_id': buy_in_id,
                                                 'balance_difference': 1_000_000}]},
        headers={'Authorization': f'Bearer {join_token}'})

    assert response.status_code == 401
    assert _remaining(session_db, buy_in_id) == 1000.0


def test_duplicate_sign_up_is_refused(session_db):
    assert session_db.add_user('bob', 'hash', 'salt', 1000)
    assert not session_db.add_user('bob', 'other-hash', 'salt', 1000)
