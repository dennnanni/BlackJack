"""Logging out has to stay logged out: remember=True mints a remember_token
cookie that outlives the session, so clearing the session alone would let the
next request silently log the player back in.
"""
from central_server import auth, db
from central_server.app import create_app


def _client(session_db):
    hashed, salt = auth.generate_hashed_password('pw')
    session_db.add_user('alice', hashed, salt, 100)
    app = create_app()
    client = app.test_client()
    client.post('/login', data={'username': 'alice', 'password': 'pw'})
    return client


def test_logout_lands_on_the_login_page_and_stays_there(session_db):
    client = _client(session_db)
    assert client.get('/user/alice').status_code == 200

    client.post('/logout')

    # Not a redirect back to /user/alice: the remember cookie is gone too.
    assert client.get('/login').status_code == 200
    assert client.get('/user/alice').headers['Location'] == '/login'


def test_login_survives_the_session_cookie_expiring(session_db):
    """The other half of remember=True: closing the browser must not log the
    player out, or coming back from a game server would land on /login."""
    client = _client(session_db)
    client.delete_cookie('central_session')

    assert client.get('/user/alice').status_code == 200
