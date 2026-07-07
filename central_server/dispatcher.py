"""Picks the game server a player is dispatched to: least-connections over
the servers whose heartbeats are fresh and that still have free seats.
"""
from central_server import db
from central_server.config import HEARTBEAT_TTL


def pick_server():
    servers = db.get_live_servers(HEARTBEAT_TTL)
    return min(servers, key=lambda s: s.load) if servers else None
