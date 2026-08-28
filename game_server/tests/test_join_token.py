"""A join token only opens the door of the server it was minted for, and
only while it is fresh (conftest pins SHARED_SECRET to 'test-secret').
"""
import time

import jwt
import pytest

from game_server.join import JoinError, verify_join_token

SECRET = 'test-secret'
MY_SERVER = 7


def _token(server_id=MY_SERVER, expires_in=120, secret=SECRET, typ='join'):
    now = int(time.time())
    claims = {'sub': 'alice', 'balance': 1000.0, 'server_id': server_id,
              'iat': now, 'exp': now + expires_in}
    if typ is not None:
        claims['typ'] = typ
    return jwt.encode(claims, secret, algorithm='HS256')


def test_valid_token_is_accepted():
    payload = verify_join_token(_token(), MY_SERVER)
    assert payload['sub'] == 'alice'
    assert payload['balance'] == 1000.0


def test_token_for_another_server_is_rejected():
    with pytest.raises(JoinError) as exc_info:
        verify_join_token(_token(server_id=MY_SERVER + 1), MY_SERVER)
    assert exc_info.value.status == 403


def test_expired_token_is_rejected():
    with pytest.raises(JoinError) as exc_info:
        verify_join_token(_token(expires_in=-10), MY_SERVER)
    assert exc_info.value.status == 401


def test_forged_token_is_rejected():
    with pytest.raises(JoinError) as exc_info:
        verify_join_token(_token(secret='not-the-shared-secret'), MY_SERVER)
    assert exc_info.value.status == 401


def test_a_server_token_cannot_be_used_to_walk_in_as_a_player():
    """Both token kinds are HS256 over the same secret, so the signature alone
    proves nothing about which door the holder may open."""
    now = int(time.time())
    server_token = jwt.encode({'typ': 'server', 'server_id': MY_SERVER,
                               'iat': now, 'exp': now + 60}, SECRET, algorithm='HS256')
    with pytest.raises(JoinError) as exc_info:
        verify_join_token(server_token, MY_SERVER)
    assert exc_info.value.status == 401


def test_an_untyped_token_is_rejected():
    """Pre-fix tokens carried no class at all: they must not be honoured."""
    with pytest.raises(JoinError) as exc_info:
        verify_join_token(_token(typ=None), MY_SERVER)
    assert exc_info.value.status == 401
