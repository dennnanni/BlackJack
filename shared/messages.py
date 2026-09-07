"""Wire contract shared by the central server and the game servers."""
from dataclasses import asdict, dataclass

# JSON field names
SUCCESS = 'success'
ERROR = 'error'
TOKEN = 'token'
ENCRYPTED = 'encrypted'
SERVER_ID = 'server_id'
HOST = 'host'
PORT = 'port'
CAPACITY = 'capacity'
PLAYERS = 'players'  # usernames seated on a game server; its load is their count
ROUND_ID = 'round_id'
RESULTS = 'results'
# Token class. Both JWT kinds are HS256 over the same SHARED_SECRET, so
# without this claim a *join* token — which the player's own browser holds —
# is a structurally valid *server* token: it even carries a server_id.
TYP = 'typ'
TYP_JOIN = 'join'
TYP_SERVER = 'server'
USERNAME = 'username'
BALANCE = 'balance'
BALANCE_DIFFERENCE = 'balance_difference'


@dataclass
class Server:
    """What a game server sends to register itself."""
    ip: str
    port: int
    key: str

    def get_url(self):
        return f'http://{self.ip}:{self.port}'

    def to_dict(self):
        return asdict(self)


@dataclass
class Result:
    """Balance change for one player produced by one finished round."""
    username: str
    balance_difference: float

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(data):
        return Result(username=data[USERNAME],
                      balance_difference=float(data[BALANCE_DIFFERENCE]))
