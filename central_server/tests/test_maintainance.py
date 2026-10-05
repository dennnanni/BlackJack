import time

import jwt
import requests

from central_server import auth, maintainance
from central_server.config import HEARTBEAT, SHARED_SECRET
from shared.messages import SERVER_ID, TYP, TYP_CENTRAL, TYP_SERVER


class _Response:
    def __init__(self, status_code):
        self.status_code = status_code


def _server_token(server_id=None):
    now = int(time.time())
    claims = {TYP: TYP_SERVER, 'iat': now, 'exp': now + 60}
    if server_id is not None:
        claims[SERVER_ID] = server_id
    return {'Authorization': f'Bearer {jwt.encode(claims, SHARED_SECRET, algorithm="HS256")}'}


def _client():
    from central_server.app import create_app
    return create_app().test_client()


def test_register_stores_the_internal_url(session_db):
    client = _client()
    body = {'host': '127.0.0.1', 'port': 8000, 'capacity': 10,
            'internal_url': 'http://game_server_1:8000'}

    server_id = client.post('/api/servers/register', json=body,
                            headers=_server_token()).get_json()[SERVER_ID]
    assert session_db.get_server(server_id).internal_url == 'http://game_server_1:8000'

    # a restart may come back at another address
    body['internal_url'] = 'http://game_server_1:9000'
    client.post('/api/servers/register', json=body, headers=_server_token(server_id))
    assert session_db.get_server(server_id).internal_url == 'http://game_server_1:9000'


def test_central_token_is_bound_to_one_server():
    payload = jwt.decode(auth.create_central_token(7), SHARED_SECRET, algorithms=['HS256'])

    assert payload[TYP] == TYP_CENTRAL
    assert payload[SERVER_ID] == 7


def test_shutdown_goes_to_the_internal_url_with_a_central_token(session_db, monkeypatch):
    server_id = session_db.register_server('127.0.0.1', 8000, 10, 'http://game_server_1:8000')
    calls = []
    monkeypatch.setattr(requests, 'post',
                        lambda url, headers, timeout: calls.append((url, headers)) or _Response(202))

    assert maintainance.send_shutdown(session_db.get_server(server_id))
    url, headers = calls[0]
    assert url == 'http://game_server_1:8000/api/shutdown'
    token = headers['Authorization'].removeprefix('Bearer ')
    assert jwt.decode(token, SHARED_SECRET, algorithms=['HS256'])[SERVER_ID] == server_id


def test_shutdown_falls_back_to_the_public_address(session_db, monkeypatch):
    server_id = session_db.register_server('127.0.0.1', 8000, 10)  # registered before the column
    calls = []
    monkeypatch.setattr(requests, 'post',
                        lambda url, headers, timeout: calls.append(url) or _Response(202))

    maintainance.send_shutdown(session_db.get_server(server_id))
    assert calls == ['http://127.0.0.1:8000/api/shutdown']


def test_shutdown_fails_when_the_server_is_unreachable_or_refuses(session_db, monkeypatch):
    server = session_db.get_server(session_db.register_server('127.0.0.1', 8000, 10))

    def unreachable(*args, **kwargs):
        raise requests.ConnectionError('refused')
    monkeypatch.setattr(requests, 'post', unreachable)
    assert not maintainance.send_shutdown(server)

    monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: _Response(403))
    assert not maintainance.send_shutdown(server)


def test_shutdown_is_resent_only_to_live_servers_under_maintainance(session_db):
    live = session_db.register_server('127.0.0.1', 8000, 10)
    stopped = session_db.register_server('127.0.0.1', 8001, 10)
    session_db.register_server('127.0.0.1', 8002, 10)  # not under maintainance
    session_db.set_server_maintainance(live)
    session_db.set_server_maintainance(stopped)
    with session_db.SessionLocal() as session:
        session.get(session_db.GameServer, stopped).last_seen = time.time() - HEARTBEAT - 5
        session.commit()

    assert [s.id for s in session_db.get_servers_to_shut_down()] == [live]


def test_panel_reports_whether_the_game_server_was_reached(session_db, monkeypatch):
    server_id = session_db.register_server('127.0.0.1', 8000, 10)
    client = _client()
    client.post('/admin/login', data={'username': 'admin', 'password': 'admin'})

    monkeypatch.setattr(maintainance, 'send_shutdown', lambda server: False)
    response = client.post(f'/admin/servers/{server_id}/maintainance')
    # dispatch stops even if the game server did not answer
    assert response.get_json() == {'success': True, 'reached': False}
    assert session_db.get_alive_servers() == []

    monkeypatch.setattr(maintainance, 'send_shutdown', lambda server: True)
    response = client.post(f'/admin/servers/{server_id}/maintainance')
    assert response.get_json()['reached']


def _state(session_db, server_id):
    return {s['id']: s for s in session_db.list_servers()}[server_id]['state']


def test_empty_report_is_refused_unless_under_maintainance(session_db):
    server_id = session_db.register_server('127.0.0.1', 8000, 10)
    client = _client()

    # token without a server id
    assert client.post('/api/servers/empty', headers=_server_token()).status_code == 401
    # token of a server central does not know
    assert client.post('/api/servers/empty',
                       headers=_server_token(server_id + 1)).status_code == 404
    # known server, but not under maintainance
    assert client.post('/api/servers/empty',
                       headers=_server_token(server_id)).status_code == 409
    assert _state(session_db, server_id) == 'active'


def test_server_is_closing_until_idle_and_buy_ins_are_closed(session_db):
    server_id = session_db.register_server('127.0.0.1', 8000, 10)
    session_db.add_user('alice', 'pw', 'salt', 1000)
    buy_in_id, _ = session_db.create_buy_in('alice', server_id, 100)
    session_db.set_server_maintainance(server_id)
    assert _state(session_db, server_id) == 'closing'

    # e.g. a player who got a join token but never reached the table
    client = _client()
    assert client.post('/api/servers/empty', headers=_server_token(server_id)).status_code == 200
    assert _state(session_db, server_id) == 'closing'

    session_db.close_buy_in(server_id, [buy_in_id])
    assert _state(session_db, server_id) == 'maintainance'


def test_shutdown_is_not_resent_once_the_server_is_idle(session_db):
    server_id = session_db.register_server('127.0.0.1', 8000, 10)
    session_db.set_server_maintainance(server_id)
    session_db.set_server_idle(server_id)

    assert session_db.get_servers_to_shut_down() == []


def test_register_ends_the_maintainance(session_db):
    server_id = session_db.register_server('127.0.0.1', 8000, 10)
    session_db.set_server_maintainance(server_id)
    session_db.set_server_idle(server_id)

    session_db.resurrect_server(server_id, '127.0.0.1', 8000, 10)
    assert session_db.get_server(server_id).idle_time is None
    assert _state(session_db, server_id) == 'active'
