from sqlalchemy import Column, String, Integer, Float, ForeignKey, Table
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# Associazione molti-a-molti tra User e GameServer
userservers = Table(
    'userservers', Base.metadata,
    Column('username', String, ForeignKey('users.username', ondelete='CASCADE'), primary_key=True),
    Column('idserver', Integer, ForeignKey('gameserver.id', ondelete='CASCADE'), primary_key=True)
)

class User(Base):
    __tablename__ = 'users'

    username = Column(String, primary_key=True)
    password = Column(String, nullable=False)
    balance = Column(Float, default=0.0)

    servers = relationship("GameServer", secondary=userservers, back_populates="users")

class GameServer(Base):
    __tablename__ = 'gameserver'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    key = Column(String, nullable=False)

    users = relationship("User", secondary=userservers, back_populates="servers")
