import time

from central_server import auth
from central_server.config import HEARTBEAT


def _client():
    from central_server.app import create_app
    return create_app().test_client()


def _login(client, username='admin', password='admin'):
    return client.post('/admin/login', data={'username': username, 'password': password})


def _add_server(session_db, seen_ago=0):
    server_id = session_db.register_server('localhost', 8000, 10)
    with session_db.SessionLocal() as session:
        session.get(session_db.GameServer, server_id).last_seen = time.time() - seen_ago
        session.commit()
    return server_id


def test_list_servers_shows_seats_and_whether_the_server_is_alive(session_db):
    # one server with two players, one that stopped sending heartbeats
    busy_id = _add_server(session_db)
    silent_id = _add_server(session_db, seen_ago=HEARTBEAT + 5)
    session_db.take_seat('alice', busy_id)
    session_db.take_seat('bob', busy_id)

    servers = {server['id']: server for server in session_db.list_servers()}
    busy, silent = servers[busy_id], servers[silent_id]

    assert busy['seats'] == 2
    assert busy['alive']

    assert silent['seats'] == 0
    assert not silent['alive']
    assert silent['last_seen_ago'] >= HEARTBEAT + 5


def test_panel_redirects_to_login(session_db):
    client = _client()

    assert client.get('/admin/').headers['Location'].endswith('/admin/login')
    assert client.get('/admin/servers').status_code == 401


def test_wrong_credentials_are_refused(session_db):
    client = _client()

    assert _login(client, password='wrong').status_code == 401
    assert client.get('/admin/servers').status_code == 401


def test_player_called_admin_is_not_the_admin(session_db):
    hashed, salt = auth.generate_hashed_password('pw')
    session_db.add_user('admin', hashed, salt, 1000)
    client = _client()
    client.post('/login', data={'username': 'admin', 'password': 'pw'})

    assert client.get('/admin/servers').status_code == 401


def test_admin_sees_the_servers_until_logout(session_db):
    server_id = session_db.register_server('localhost', 8000, 10)
    client = _client()
    _login(client)

    response = client.get('/admin/servers')
    assert response.status_code == 200
    assert [s['id'] for s in response.get_json()['servers']] == [server_id]

    client.post('/admin/logout')
    assert client.get('/admin/servers').status_code == 401


def test_maintainance_button_requires_the_admin(session_db):
    server_id = _add_server(session_db)
    client = _client()

    assert client.post(f'/admin/servers/{server_id}/maintainance').status_code == 401
    assert session_db.list_servers()[0]['maintainance_since'] is None


def test_admin_starts_the_maintainance(session_db):
    server_id = _add_server(session_db)
    client = _client()
    _login(client)

    assert client.post(f'/admin/servers/{server_id + 1}/maintainance').status_code == 404
    assert client.post(f'/admin/servers/{server_id}/maintainance').status_code == 200

    server = client.get('/admin/servers').get_json()['servers'][0]
    assert server['maintainance_since'] is not None
