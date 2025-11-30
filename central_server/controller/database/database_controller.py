from central_server.model.database_actions import add_user, get_user, is_user_playing
from central_server.model.structures import UserInfo

def register_user(username, password, salt, balance):
    if not username or not password or not salt or balance < 0.0:
        return 'Username, password, salt must be non-empty and balance must be non-negative'
    result = add_user(username, password, salt, balance)
    return result

def get_salt(username):
    if not username:
        return None, 'Username is required to get salt'
    user = get_user(username)
    if user:
        return user.salt, None
    return None, 'User not found'

def login_user(username, password):
    user_db = get_user(username)
    # TODO check if user is in db
    if password == user_db.password:
        return True
    else:
        return f'Wrong password for user: {username}'\
    
def get_user_info(username):
    if not username:
        return 'Username is required to get info'
    
    user = get_user(username)
    if user:
        return UserInfo(user.username, user.balance)
    else:
        return f'User {username} not found'
    
def user_playing(username):
    if not username:
        return 'Username is required to get player status'
    
    playing = is_user_playing(username)
    return playing

