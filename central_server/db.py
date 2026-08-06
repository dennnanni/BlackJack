"""Database layer of the central server: engine, ORM models and the
data-access functions that the web/API blueprints call directly (no HTTP).

Nothing here swallows database errors: a failing query raises and Flask turns
that into a 500, rather than a silent None the callers mistake for "no data".
"""
import time
from decimal import Decimal

from sqlalchemy import Column, Float, Integer, Numeric, String, create_engine
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
    with SessionLocal() as session:
        session.add(User(username=username, password=password, salt=salt, balance=balance))
        session.commit()


def get_user(username):
    with SessionLocal() as session:
        return session.get(User, username)


def register_server(host, port, capacity):
    """Insert a new game server; returns its assigned id."""
    with SessionLocal() as session:
        server = GameServer(host=host, port=port, capacity=capacity,
                            load=0, last_seen=time.time())
        session.add(server)
        session.commit()
        return server.id


def heartbeat(server_id, load):
    """Record a heartbeat; returns False if the server id is unknown."""
    with SessionLocal() as session:
        server = session.get(GameServer, server_id)
        if server is None:
            return False
        server.load = load
        server.last_seen = time.time()
        session.commit()
    return True


def get_live_servers(ttl):
    """Servers heard from within `ttl` seconds that still have free seats."""
    with SessionLocal() as session:
        return session.query(GameServer).filter(
            GameServer.last_seen >= time.time() - ttl,
            GameServer.load < GameServer.capacity,
        ).all()


def apply_results(round_id, results):
    """Idempotently apply the additive balance deltas of one round.

    Replaying a round_id returns without re-applying, so the sender can keep
    retrying safely. The ledger check and the balance updates commit
    atomically: a concurrent duplicate delivery dies on the primary-key
    conflict instead of double-applying.
    """
    with SessionLocal() as session:
        if session.get(AppliedRound, round_id):
            return  # duplicate delivery: ACK again, change nothing
        for result in results:
            user = session.get(User, result.username)
            if user:
                user.balance += Decimal(str(result.balance_difference))
        session.add(AppliedRound(round_id=round_id, applied_at=time.time()))
        session.commit()


def prune_applied_rounds(max_age):
    """Drop ledger entries old enough that no retry can still be in flight."""
    with SessionLocal() as session:
        session.query(AppliedRound).filter(
            AppliedRound.applied_at < time.time() - max_age).delete()
        session.commit()
