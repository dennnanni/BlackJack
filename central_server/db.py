"""Database layer of the central server."""
from decimal import Decimal

from sqlalchemy import (Column, ForeignKey, Integer, Numeric, String, Table,
                        create_engine, func, literal)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from central_server.config import DATABASE_URL

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
    ip = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    key = Column(String, nullable=False)

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


def get_servers_with_user_count():
    """Every registered server with the number of players connected to it and
    the maximum it accepts."""
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


def register_server(server):
    """Insert a new game server; returns its assigned id."""
    with SessionLocal() as session:
        session.add(server)
        session.commit()
        return server.id


def get_server_key(server_id):
    """The key of a registered server, or None if there is no such server."""
    with SessionLocal() as session:
        server = session.get(GameServer, server_id)
        return server.key if server else None


def update_users_balance(results):
    """Apply each result's balance change to its player."""
    with SessionLocal() as session:
        for result in results:
            user = session.get(User, result.username)
            if user:
                user.balance += Decimal(str(result.balance_difference))
        session.commit()
