"""Database layer of the central server: engine, ORM models and the
data-access functions that the web/API blueprints call directly (no HTTP).
"""
import time
from decimal import Decimal

from sqlalchemy import Column, Float, Integer, Numeric, String, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from central_server.config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = 'user'

    username = Column(String, primary_key=True)
    password = Column(String, nullable=False)
    salt = Column(String, nullable=False)
    balance = Column(Numeric(10, 2), default=0.0)


class GameServer(Base):
    __tablename__ = 'gameserver'

    id = Column(Integer, primary_key=True, autoincrement=True)
    host = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    capacity = Column(Integer, nullable=False, default=10)
    # Reported by the server's own heartbeats, not computed by central.
    load = Column(Integer, nullable=False, default=0)
    last_seen = Column(Float, nullable=False, default=0.0)  # unix timestamp


def init_db():
    Base.metadata.create_all(bind=engine)


def add_user(username, password, salt, balance):
    try:
        with SessionLocal() as session:
            session.add(User(username=username, password=password, salt=salt, balance=balance))
            session.commit()
        return True
    except SQLAlchemyError as e:
        print(f'Error adding user: {e}')
        return False


def get_user(username):
    try:
        with SessionLocal() as session:
            return session.get(User, username)
    except SQLAlchemyError as e:
        print(f'Error retrieving user: {e}')
        return None


def register_server(host, port, capacity):
    """Insert a new game server; returns its assigned id, or None on failure."""
    try:
        with SessionLocal() as session:
            server = GameServer(host=host, port=port, capacity=capacity,
                                load=0, last_seen=time.time())
            session.add(server)
            session.commit()
            return server.id
    except SQLAlchemyError as e:
        print(f'Error registering server: {e}')
        return None


def heartbeat(server_id, load):
    """Record a heartbeat; returns False if the server id is unknown."""
    try:
        with SessionLocal() as session:
            server = session.get(GameServer, server_id)
            if server is None:
                return False
            server.load = load
            server.last_seen = time.time()
            session.commit()
        return True
    except SQLAlchemyError as e:
        print(f'Error recording heartbeat: {e}')
        return False


def get_live_servers(ttl):
    """Servers heard from within `ttl` seconds that still have free seats."""
    try:
        with SessionLocal() as session:
            return session.query(GameServer).filter(
                GameServer.last_seen >= time.time() - ttl,
                GameServer.load < GameServer.capacity,
            ).all()
    except SQLAlchemyError as e:
        print(f'Error retrieving live servers: {e}')
        return []


def get_servers():
    try:
        with SessionLocal() as session:
            return session.query(GameServer).all()
    except SQLAlchemyError as e:
        print(f'Error retrieving servers: {e}')
        return []


def update_users_balance(results):
    """Apply additive balance deltas for a list of Result records."""
    try:
        with SessionLocal() as session:
            for result in results:
                user = session.get(User, result.username)
                if user:
                    user.balance += Decimal(str(result.balance_difference))
            session.commit()
        return True
    except SQLAlchemyError as e:
        print(f'Error updating user balances: {e}')
        return False
