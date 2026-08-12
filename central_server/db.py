"""Database layer of the central server: the engine, the ORM models and the
data-access functions the blueprints call directly.
"""
from central_server.config import DATABASE_URL
from sqlalchemy import (Column, ForeignKey, Integer, Numeric, String, Table,
                        create_engine, func, literal)
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# many-to-many relationship between users and servers
userservers = Table(
    'userserver', Base.metadata,
    Column('username', String, ForeignKey('user.username', ondelete='CASCADE'), primary_key=True),
    Column('idserver', Integer, ForeignKey('gameserver.id', ondelete='CASCADE'), primary_key=True)
)


class User(Base):
    __tablename__ = 'user'

    username = Column(String, primary_key=True)
    password = Column(String, nullable=False)
    salt = Column(String, nullable=False)
    balance = Column(Numeric(10, 2), default=0.0)

    servers = relationship("GameServer", secondary=userservers, back_populates="users")


class GameServer(Base):
    __tablename__ = 'gameserver'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    key = Column(String, nullable=False)

    users = relationship("User", secondary=userservers, back_populates="servers")


def init_db():
    Base.metadata.create_all(bind=engine)


def add_user(username, password, salt, balance):
    """
    Adds a user to the database.
    """
    try:
        new_user = User(username=username, password=password, balance=balance, salt=salt)
        with SessionLocal() as session:
            session.add(new_user)
            session.commit()
        return True
    except SQLAlchemyError as e:
        print(f'Error adding user: {e}')
        return str(e)


def get_user(username):
    """
    Retrieves a user from the database, or None if there is no such user.
    """
    try:
        with SessionLocal() as session:
            return session.query(User).filter(User.username == username).first()
    except SQLAlchemyError as e:
        print(f'Error retrieving user: {e}')
        return None


def get_servers_with_user_count():
    """
    Retrieves the list of servers with connected users count from the database.

    Returns:
        list: id, ip and port of the server, number of users connected to it
        and the maximum number of players accepted.
    """
    try:
        with SessionLocal() as session:
            return session.query(
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
    except SQLAlchemyError as e:
        print(f'Error retrieving active servers: {e}')
        return None


def register_server(server):
    """
    Registers a new server in the database and returns its assigned id.
    """
    try:
        with SessionLocal() as session:
            session.add(server)
            session.commit()
            session.refresh(server)
        return server.id
    except SQLAlchemyError as e:
        print(f'Error registering server: {e}')
        return False


def get_server_key(server_id):
    """
    Retrieves the key of a server by its ID.
    """
    try:
        with SessionLocal() as session:
            server = session.query(GameServer).filter(GameServer.id == server_id).first()
            return server.key if server else None
    except SQLAlchemyError as e:
        print(f'Error retrieving server key: {e}')
        return None


def update_users_balance(results):
    """
    Updates the balances of users based on the results.
    """
    try:
        with SessionLocal() as session:
            for result in results:
                user = session.query(User).filter(User.username == result.username).first()
                if user:
                    user.balance += result.balance_difference
            session.commit()
            return True
    except SQLAlchemyError as e:
        print(f'Error updating user balances: {e}')
        return False
