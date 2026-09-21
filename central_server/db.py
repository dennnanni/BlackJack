"""Database layer of the central server."""
from decimal import ROUND_DOWN, Decimal, InvalidOperation
import time
import uuid
import logging

from sqlalchemy import (Column, Float, ForeignKey, Index, Integer, Numeric, String,
                        Table, create_engine, func, literal, or_, update)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from central_server.config import DATABASE_URL, HEARTBEAT, SEAT_GRACE, SEAT_TAKEOVER
from shared.messages import BUY_IN_ID, ERROR

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

logger = logging.getLogger(__name__)

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
    load = Column(Integer, nullable=False, default=0)
    last_seen = Column(Float, nullable=False, default=0.0)

class Seat(Base):
    __tablename__ = 'seat'

    username = Column(String, primary_key=True)
    server_id = Column(Integer, nullable=False)
    since = Column(Float, nullable=False)


class BuyIn(Base):
    __tablename__ = 'buyin'

    id = Column(String, primary_key=True)
    username = Column(String, nullable=False)
    server_id = Column(Integer, nullable=False)
    initial = Column(Numeric(10, 2), nullable=False)
    remaining = Column(Numeric(10, 2), nullable=False)
    last_updated = Column(Float, nullable=False)
    closed_at = Column(Float)

    __table_args__ = (
        Index('idx_open_buy_in', 'username', 'server_id', unique=True,
              postgresql_where=closed_at.is_(None),
              sqlite_where=closed_at.is_(None)),
    )

# keeps the list of rounds that have already been applied to avoid duplicates
class AppliedRound(Base):
    __tablename__ = 'applied_round'

    round_id = Column(String, primary_key=True)
    applied_at = Column(Float, nullable=False)

class UnappliedResult(Base):
    __tablename__ = 'unapplied_result'

    id = Column(Integer, primary_key=True, autoincrement=True)
    round_id = Column(String, nullable=False)
    server_id = Column(Integer, nullable=False)
    username = Column(String, nullable=False)
    buy_in_id = Column(String)
    balance_difference = Column(Numeric(10, 2), nullable=False)
    reason = Column(String, nullable=False)
    recorded_at = Column(Float, nullable=False)


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

def resurrect_server(server_id, host, port, capacity):
    with SessionLocal() as session:
        server = session.get(GameServer, server_id)
        if server is None:
            return False
        server.host = host
        server.capacity = capacity
        server.port = port
        server.last_seen = time.time()
        return server_id


def update_heartbeat(server_id, players):
    """Record a heartbeat and update seated players"""
    with SessionLocal() as session:
        server = session.get(GameServer, server_id)
        if server is None:
            return False

        server.load = len(players)
        server.last_seen = time.time()
        session.query(Seat).filter(
            Seat.server_id == server_id,
            Seat.since < time.time() - SEAT_GRACE,
            Seat.username.notin_(players)
        ).delete()

        session.commit()
        return True


def get_alive_servers():
    with SessionLocal() as session:
        return session.query(GameServer).filter(
            GameServer.last_seen >= time.time() - HEARTBEAT,
            GameServer.load < GameServer.capacity
        ).all()

def take_seat(username, server_id):
    """Add new player seat if player not seated or update the existing one if
    game server not available and takeover expired."""
    with SessionLocal() as session:
        seat = session.get(Seat, username, with_for_update=True)
        if seat is not None:
            owner = session.get(GameServer, seat.server_id)
            owner_alive = owner is not None and owner.last_seen >= time.time() - SEAT_TAKEOVER
            if seat.server_id != server_id and owner_alive:
                return False
            seat.server_id = server_id
            seat.since = time.time()
            session.commit()
            return True
        
        session.add(Seat(username=username, server_id=server_id, since=time.time()))
        try:
            session.commit()
        except:
            return False
        return True

def create_buy_in(username, server_id, buy_in):
    """Creates the buy in row reserving an amount from the user balance"""
    with SessionLocal() as session:
        user = session.get(User, username)
        if user is None:
            raise ValueError('Unknown user')

        try:
            amount = Decimal(str(buy_in))
        except:
            raise ValueError('Buy in amount is not a valid number')
        
        if amount <= 0:
            raise ValueError('Buy in amount cannot be negative or zero')
        if amount > user.balance:
            raise ValueError('User buy in amount cannot exceed user balance')

        id = str(uuid.uuid4())
        user.balance -= amount # reserves the buy in from the balance
        session.add(BuyIn(id=id, username=username, server_id=server_id,
                          initial=amount, remaining=amount,
                          last_updated=time.time()))
        try:
            session.commit()
        except:
            # if it ends up here the unique index has raised
            session.rollback()
            raise ValueError('You already have an open buy in on that table')
        return id, amount


def _settle(session, buy_in):
    """Hand what is left of a buy in back to its player."""
    remaining = buy_in.remaining
    if remaining < 0:
        logger.error('Buy in remaining amount is negative, capping it to zero')
        remaining = 0
    session.execute(
        update(User)
        .where(User.username == buy_in.username)
        .values(balance=User.balance + remaining))
    now = time.time()
    buy_in.closed_at = now
    buy_in.last_updated = now


def close_buy_in(server_id, buy_in_ids):
    """Closes the buy ins of the given ids"""
    closed = []
    with SessionLocal() as session:
        for id in buy_in_ids:
            buy_in = session.get(BuyIn, id, with_for_update=True)
            if buy_in is None:
                closed.append(id)
                continue
            if buy_in.server_id == server_id:
                continue
            if buy_in.closed_at is None:
                _settle(session, buy_in)
            closed.append(id)
        session.commit()
    return closed


def close_abandoned_buy_ins(grace):
    """Settle open buy ins that no game server is holding any more"""
    with SessionLocal() as session:
        seat_held = session.query(Seat).filter(
            Seat.username == BuyIn.username,
            Seat.server_id == BuyIn.server_id).exists()
        server_alive = session.query(GameServer).filter(
            GameServer.id == BuyIn.server_id,
            GameServer.last_seen >= time.time() - SEAT_TAKEOVER).exists()
        abandoned = session.query(BuyIn).filter(
            BuyIn.closed_at.is_(None),
            BuyIn.last_updated < time.time() - grace,
            or_(~seat_held, ~server_alive)).with_for_update().all()

        closed = [buy_in.id for buy_in in abandoned]
        for buy_in in abandoned:
            _settle(session, buy_in)
        session.commit()
    return closed

def _get_buy_in(session, server_id, result):
    buy_in = session.get(BuyIn, result.buy_in_id, with_for_update=True)
    if buy_in is None:
        return None, 'Unknown buy in'
    if buy_in.server_id != server_id:
        return None, 'Buy in belong to another server'
    if buy_in.username != result.username:
        return None, 'Buy in belongs to another user'
    return buy_in, None


def apply_round(round_id, server_id, results):
    """Apply each result's balance change to its player exactly once."""
    with SessionLocal() as session:
        if session.get(AppliedRound, round_id) is not None:
            return
        now = time.time()
        rejected = []
        for result in results:
            buy_in, reason = _get_buy_in(session, server_id, result)
            if buy_in is None:
                session.add(UnappliedResult(
                    round_id = round_id, server_id=server_id, 
                    username=result.username, buy_in_id=result.buy_in_id,
                    balance_difference=Decimal(str(result.balance_difference)),
                    reason=reason, recorded_at=now
                ))
                rejected.append({BUY_IN_ID: result.buy_in_id, ERROR: reason})
                logger.error(f'Server {server_id} reported a result for {result.username} with no buy in in that server')
                continue

            difference = Decimal(str(result.balance_difference))
            # cap the win if something went wrong and the table let the player stake more than available
            if difference > buy_in.remaining:
                logger.error(f'Server {server_id} reported a win of {difference} for '
                            f'{result.username} on a buy in holding {buy_in.remaining}')
                difference = buy_in.remaining
            # cap to the max loss of the table
            charge = max(difference, -buy_in.remaining)

            # applies the difference directly on the user balance
            if buy_in.closed_at is not None:
                session.execute(
                    update(User)
                    .where(User.username == result.username)
                    .values(balance=User.balance + charge))

            buy_in.remaining = buy_in.remaining + charge
            buy_in.last_updated = now

        session.add(AppliedRound(round_id=round_id, applied_at=now))
        session.commit()
        return rejected

def prune_old_rounds(max_age):
    """Drop applied rounds entries old enough that no retry can still happen"""
    with SessionLocal() as session:
        session.query(AppliedRound).filter(
            AppliedRound.applied_at < time.time() - max_age).delete()
        session.commit()
