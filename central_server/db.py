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


class AppliedRound(Base):
    """Idempotency ledger: round ids whose results were already applied.

    Game servers deliver results at-least-once (they retry until ACKed), so
    this ledger is what turns duplicates into no-ops: exactly-once effect.
    """
    __tablename__ = 'applied_round'

    round_id = Column(String, primary_key=True)
    applied_at = Column(Float, nullable=False)  # unix timestamp


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


def apply_results(round_id, results):
    """Idempotently apply the additive balance deltas of one round.

    Returns True if the round is applied *or was already applied* (both mean
    the sender can safely stop retrying), False on error. The ledger check and
    the balance updates commit atomically: a concurrent duplicate delivery
    dies on the primary-key conflict instead of double-applying.
    """
    try:
        with SessionLocal() as session:
            if session.get(AppliedRound, round_id):
                return True  # duplicate delivery: ACK again, change nothing
            for result in results:
                user = session.get(User, result.username)
                if user:
                    user.balance += Decimal(str(result.balance_difference))
            session.add(AppliedRound(round_id=round_id, applied_at=time.time()))
            session.commit()
        return True
    except SQLAlchemyError as e:
        print(f'Error applying round {round_id}: {e}')
        return False


def prune_applied_rounds(max_age):
    """Drop ledger entries old enough that no retry can still be in flight."""
    try:
        with SessionLocal() as session:
            session.query(AppliedRound).filter(
                AppliedRound.applied_at < time.time() - max_age).delete()
            session.commit()
    except SQLAlchemyError as e:
        print(f'Error pruning applied rounds: {e}')
