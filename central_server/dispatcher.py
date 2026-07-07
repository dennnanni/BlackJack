"""Picks the game server a player is dispatched to."""
import random

from central_server import db


def pick_server():
    """Interim policy: any registered server (load-aware pick arrives with heartbeats)."""
    servers = db.get_servers()
    return random.choice(servers) if servers else None
