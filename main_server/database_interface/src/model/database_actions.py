from sqlalchemy.exc import SQLAlchemyError
from src import SessionLocal, engine
from src.orm.orm import Base, User

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