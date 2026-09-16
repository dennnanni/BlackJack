"""Database layer of the central server."""
from decimal import Decimal
import time
import uuid

from sqlalchemy import (Column, Float, ForeignKey, Integer, Numeric, String, Table,
                        create_engine, func, literal, update)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from central_server.config import DATABASE_URL, HEARTBEAT, SEAT_GRACE, SEAT_TAKEOVER

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
    username = Column(String, ForeignKey('user.username'))
    server_id = Column(Integer)
    initial = Column(Numeric(10, 2), nullable=False)
    remaining = Column(Numeric(10, 2), nullable=False)
    last_updated = Column(Float, nullable=False)
    closed_at = Column(Float)

# keeps the list of rounds that have already been applied to avoid duplicates
class AppliedRound(Base):
    __tablename__ = 'applied_round'

    round_id = Column(String, primary_key=True)
    applied_at = Column(Float, nullable=False)

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
    with SessionLocal() as session:
        user = session.get(User, username)
        if buy_in > user.balance:
            raise ValueError('User buy in amount cannot exceed user balance')
        if buy_in <= 0:
            raise ValueError('Buy in amount cannot be negative or zero')
        
        amount = Decimal(str(buy_in))
        id = str(uuid.uuid4())
        user.balance -= amount # reserves the buy in from the balance
        buy_in = BuyIn(id=id, username=username, server_id=server_id, initial=amount, remaining=amount, 
                       last_updated=time.time())
        session.add(buy_in)
        session.commit()
        return id

def close_buy_in(server_id, buy_in_ids):
    """Delete the buy in entries re-enstating the money in user balance"""
    with SessionLocal() as session:
        for id in buy_in_ids:
            buy_in = session.get(BuyIn, id)
            if buy_in and buy_in.server_id == server_id and buy_in.closed_at is None:
                session.execute(
                    update(User)
                    .where(User.username == buy_in.username)
                    .values(balance=User.balance + buy_in.remaining))
                buy_in.remaining = 0
                now = time.time()
                buy_in.closed_at = now
                buy_in.last_updated = now
        session.commit()
        

def apply_round(round_id, server_id, results):
    """Apply each result's balance change to its player exactly once."""
    with SessionLocal() as session:
        if session.get(AppliedRound, round_id) is not None:
            return
        now = time.time()
        for result in results:
            difference = Decimal(str(result.balance_difference))
            charged = session.execute(
                update(BuyIn)
                .where(BuyIn.username == result.username)
                .where(BuyIn.server_id == server_id)
                .where(BuyIn.closed_at.is_(None))
                .values(remaining=BuyIn.remaining + difference,
                        last_updated=now))
            if charged.rowcount == 0:
                session.execute(
                    update(User)
                    .where(User.username == result.username)
                    .values(balance=User.balance + difference))
        session.add(AppliedRound(round_id=round_id, applied_at=now))
        session.commit()

def prune_old_rounds(max_age):
    """Drop applied rounds entries old enough that no retry can still happen"""
    with SessionLocal() as session:
        session.query(AppliedRound).filter(
            AppliedRound.applied_at < time.time() - max_age).delete()
        session.commit()
