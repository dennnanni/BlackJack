"""Database layer of the central server: engine, ORM models and the
data-access functions that the web/API blueprints call directly (no HTTP).

Nothing here swallows database errors: a failing query raises and Flask turns
that into a 500, rather than a silent None the callers mistake for "no data".
"""
import time
from decimal import Decimal

from sqlalchemy import (Column, Float, Integer, Numeric, String, create_engine,
                        update)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base, sessionmaker

from central_server.config import DATABASE_URL, SEAT_GRACE

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


class Seat(Base):
    """The one game server a player currently occupies a seat on.

    The username is the primary key, so the table *is* the mutual exclusion:
    one account can be seated at one table at a time, and therefore cannot
    stake the same balance twice on two servers. Claimed at dispatch,
    refreshed by the owning server's heartbeats, released when that server
    stops reporting the player.
    """
    __tablename__ = 'seat'

    username = Column(String, primary_key=True)
    server_id = Column(Integer, nullable=False)
    since = Column(Float, nullable=False)  # unix timestamp of the claim


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


def heartbeat(server_id, players):
    """Record a heartbeat carrying the server's seated players.

    The player list doubles as the seat-lease renewal: whoever this server no
    longer reports has left the table and their seat is released, so they can
    be dispatched again. Returns False if the server id is unknown.
    """
    with SessionLocal() as session:
        server = session.get(GameServer, server_id)
        if server is None:
            return False
        server.load = len(players)
        server.last_seen = time.time()

        # Release the seats this server no longer claims. Seats younger than
        # SEAT_GRACE are spared: they belong to players who were just
        # dispatched and have not landed on the server yet.
        session.query(Seat).filter(
            Seat.server_id == server_id,
            Seat.since < time.time() - SEAT_GRACE,
            Seat.username.notin_(players),
        ).delete(synchronize_session=False)
        session.commit()
    return True


def take_seat(username, server_id, ttl):
    """Claim `username`'s single seat for `server_id`; False if refused.

    Refused when the player already holds a seat on a server that is still
    live: that is what keeps one account on one table. A seat whose owner
    stopped heartbeating (crashed, or partitioned away and thus unreachable
    for a new round anyway) is taken over instead of locking the player out
    forever. Two concurrent claims race on the primary key, so exactly one
    of them wins.

    The row is read FOR UPDATE because the primary key only arbitrates the
    *insert* path. Taking over an existing seat is a read-modify-write, and
    two concurrent takeovers of the same dead server's seat would both commit
    — landing one account on two tables, the exact thing this table exists to
    prevent. The lock serialises them so the second sees the first's write.
    """
    with SessionLocal() as session:
        seat = session.get(Seat, username, with_for_update=True)
        if seat is not None:
            owner = session.get(GameServer, seat.server_id)
            owner_live = owner is not None and owner.last_seen >= time.time() - ttl
            if seat.server_id != server_id and owner_live:
                return False
            seat.server_id = server_id
            seat.since = time.time()
            session.commit()
            return True
        session.add(Seat(username=username, server_id=server_id, since=time.time()))
        try:
            session.commit()
        except IntegrityError:  # someone else claimed the seat first
            return False
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

    Each delta is applied by the database itself (`SET balance = balance + d`),
    never read-modify-written in Python: two rounds of the same player landing
    concurrently would otherwise overwrite each other's update.
    """
    with SessionLocal() as session:
        if session.get(AppliedRound, round_id):
            return  # duplicate delivery: ACK again, change nothing
        for result in results:
            session.execute(
                update(User)
                .where(User.username == result.username)
                .values(balance=User.balance + Decimal(str(result.balance_difference))))
        session.add(AppliedRound(round_id=round_id, applied_at=time.time()))
        session.commit()


def prune_applied_rounds(max_age):
    """Drop ledger entries old enough that no retry can still be in flight."""
    with SessionLocal() as session:
        session.query(AppliedRound).filter(
            AppliedRound.applied_at < time.time() - max_age).delete()
        session.commit()
