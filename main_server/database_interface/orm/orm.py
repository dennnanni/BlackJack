from sqlalchemy import Column, String, Integer, Float, ForeignKey, Table, Numeric
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# Associazione molti-a-molti tra User e GameServer
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
    balance = Column(Numeric(10,2), default=0.0)

    servers = relationship("GameServer", secondary=userservers, back_populates="users")

class GameServer(Base):
    __tablename__ = 'gameserver'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    key = Column(String, nullable=False)

    users = relationship("User", secondary=userservers, back_populates="servers")
