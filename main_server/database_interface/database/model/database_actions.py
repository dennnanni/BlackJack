from sqlalchemy import func, literal
from sqlalchemy.exc import SQLAlchemyError
from database import SessionLocal, engine
from database.orm.orm import Base, GameServer, User, userservers

Base.metadata.create_all(bind=engine)

def add_user(username, password, salt, balance):
    """
    Adds a user to the database.
    
    Args:
        username (str): The username of the user.
        password (str): The password of the user.
        balance (float): The balance of the user.
        salt (str): The salt for the password.
    """
    try:
        new_user = User(username=username, password=password, balance=balance, salt=salt)
        with SessionLocal() as session:
            session.add(new_user)
            session.commit()
        return True
    except SQLAlchemyError as e:
        print(f'Error adding user: {e}')
        session.rollback()
        return str(e)
    
def get_user(username):
    """
    Retrieves a user from the database.
    
    Args:
        username (str): The username of the user.
    
    Returns:
        User: The user object if found, None otherwise.
    """
    try:
        with SessionLocal() as session:
            user = session.query(User).filter(User.username == username).first()
            return user
    except SQLAlchemyError as e:
        print(f'Error retrieving user: {e}')
        return None
    
    
def get_servers_with_user_count():
    """
    Retrieves the list of servers with connected users count from the database.
    
    Returns:
        list: A list of objects that include id, ip and port of the server, 
        number of users connected to it and the maximum number of players accepted.
    """
    try:
        with SessionLocal() as session:
            result = session.query(
                GameServer.id,
                GameServer.ip,
                GameServer.port,
                func.count(User.username).label('connected_users'),
                literal(10).label('max_users'),
                GameServer.key
            ).outerjoin(
                userservers, GameServer.id == userservers.c.idserver
            ).outerjoin(
                User, userservers.c.username == User.username
            ).group_by(GameServer).all()
            
            return result
    except SQLAlchemyError as e:
        print(f'Error retrieving active servers: {e}')
        return None