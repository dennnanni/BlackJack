"""Wire contract shared by the central server and the game servers."""
from dataclasses import asdict, dataclass

# JSON field names
SUCCESS = 'success'
ERROR = 'error'
TOKEN = 'token'
ENCRYPTED = 'encrypted'
SERVER_ID = 'server_id'


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
