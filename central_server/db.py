"""Database layer of the central server."""
from decimal import Decimal
import time

from sqlalchemy import (Column, Float, ForeignKey, Integer, Numeric, String, Table,
                        create_engine, func, literal)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from central_server.config import DATABASE_URL, HEARTBEAT

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# many-to-many relationship between users and game servers
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
    host = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    capacity = Column(Integer, nullable=False, default=10)
    load = Column(Integer, nullable=False, default=0)
    last_seen = Column(Float, nullable=False, default=0.0)

    users = relationship("User", secondary=userservers, back_populates="servers")


def init_db():
    Base.metadata.create_all(bind=engine)


def add_user(username, password, salt, balance):
    with SessionLocal() as session:
        session.add(User(username=username, password=password, salt=salt, balance=balance))
        session.commit()


def get_user(username):
    with SessionLocal() as session:
        return session.get(User, username)


def register_server(host, port, capacity):
    """Insert a new game server; returns its assigned id."""
    with SessionLocal() as session:
        server = GameServer(host=host, port=port, capacity=capacity, last_seen=time.time())
        session.add(server)
        session.commit()
        return server.id


def update_heartbeat(server_id, players):
    with SessionLocal() as session:
        server = session.get(GameServer, server_id)
        if server is None:
            return False

        server.load = len(players)
        server.last_seen = time.time()
        session.commit()

        return True


def get_alive_servers():
    with SessionLocal() as session:
        return session.query(GameServer).filter(
            GameServer.last_seen >= time.time() - HEARTBEAT,
            GameServer.load < GameServer.capacity
        ).all()


def update_users_balance(results):
    """Apply each result's balance change to its player."""
    with SessionLocal() as session:
        for result in results:
            user = session.get(User, result.username)
            if user:
                user.balance += Decimal(str(result.balance_difference))
        session.commit()
