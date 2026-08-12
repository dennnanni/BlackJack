"""Player-facing web routes."""
from dataclasses import dataclass

from flask import Blueprint, redirect, render_template, request, session
from flask_login import UserMixin, current_user, login_required
from flask_login import login_user as flask_login_user

from central_server import auth, db
from central_server.config import INITIAL_BALANCE
from shared.messages import ERROR, TOKEN

# Fields of the Socket.IO replies the home page reads
DATA = 'data'
REDIRECT = 'redirect'

# Path local route
USER_HOME_PATH = '/user/'
LOGIN_PAGE_PATH = '/login'

# Path to external API
JOIN_TABLE_API_ENDPOINT = '/join'

web_bp = Blueprint('web', __name__)


@dataclass
class UserSession(UserMixin):
    username: str

    def get_id(self):
        return self.username


@dataclass
class ServerLoad:
    """A registered game server together with how many players it holds."""
    id: int
    ip: str
    port: int
    connected_users: int
    max_users: int
    key: str

    def get_url(self):
        return f'http://{self.ip}:{self.port}'


class Dispatcher:

    def __pick_server(self, servers_list):
        """
        Balance logic.
        """
        return min(servers_list, key=lambda server: server.connected_users) if servers_list else None

    def pick_game_server(self):
        servers = db.get_servers_with_user_count()
        if not servers:
            return None, 'No servers available'

        received_servers = [ServerLoad(*server) for server in servers]

        picked = self.__pick_server(received_servers)
        if not picked:
            return None, 'Servers are full'
        return picked, None


dispatcher = Dispatcher()


def login_user(username, password):
    if not username or not password:
        return {ERROR: 'Username and password are required'}

    user = db.get_user(username)
    if not user:
        return {ERROR: f'User {username} not found'}

    if auth.get_hashed_password(password, user.salt) != user.password:
        return {ERROR: f'Wrong password for user {username}'}

    flask_login_user(UserSession(username))
    return {REDIRECT: f'{USER_HOME_PATH}{username}'}


def register_user(username, password):
    if not username or not password:
        return {ERROR: 'Username and password are required'}

    hashed_password, salt = auth.generate_hashed_password(password)

    if db.add_user(username, hashed_password, salt, INITIAL_BALANCE) is not True:
        return {ERROR: f'Error adding user {username}'}

    return {REDIRECT: LOGIN_PAGE_PATH}


def get_user_info(data):
    username = data.get('username')
    if not username:
        return {ERROR: 'Username is required'}

    user = db.get_user(username)
    if not user:
        return {ERROR: f'User {username} not found'}

    # balance is a Numeric column, so SQLAlchemy returns a Decimal, which is not JSON serializable
    return {DATA: {'username': user.username, 'balance': float(user.balance)}}


def get_game_server(data):
    username = data.get('username')
    if not username:
        return {ERROR: 'Username is required'}

    user_info = get_user_info(data)
    if user_info.get(ERROR) or not user_info.get(DATA):
        return user_info

    balance = user_info.get(DATA).get('balance')
    if float(balance) <= 0:
        return {ERROR: 'User balance is zero, please add funds to play'}

    server, error = dispatcher.pick_game_server()
    if error is not None:
        return {ERROR: error}

    if not server.key:
        raise ValueError(f'Server {server.get_url()} key is not set')

    return {
        REDIRECT: server.get_url() + JOIN_TABLE_API_ENDPOINT,
        TOKEN: auth.create_token(username, server)
    }


@web_bp.route('/user/<username>')
@login_required
def index(username):
    return render_template('home.html', username=username)


@web_bp.route('/')
@web_bp.route('/login', methods=['GET'])
def login():
    if current_user.is_authenticated:
        return redirect(f'/user/{current_user.username}')
    return render_template('access.html', login=True)


@web_bp.route('/register', methods=['GET'])
def register():
    return render_template('access.html', register=True)


@web_bp.route('/login', methods=['POST'])
def login_post():
    response = login_user(request.form.get('username'), request.form.get('password'))
    return redirect(response.get(REDIRECT)) if response.get(REDIRECT) else render_template('access.html', login=True, error=response.get(ERROR))


@web_bp.route('/register', methods=['POST'])
def register_post():
    response = register_user(request.form.get('username'), request.form.get('password'))
    return redirect(response.get(REDIRECT)) if response.get(REDIRECT) else render_template('access.html', login=True, error=response.get(ERROR))


@web_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    return redirect('/login')
