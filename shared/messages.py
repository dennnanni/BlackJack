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
PLAYERS = 'players'
ROUND_ID = 'round_id'
RESULTS = 'results'
# Token class to distinguish between a server join token and a user token
TYP = 'typ'
TYP_JOIN = 'join'
TYP_SERVER = 'server'
USERNAME = 'username'
BALANCE = 'balance'
BALANCE_DIFFERENCE = 'balance_difference'

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
