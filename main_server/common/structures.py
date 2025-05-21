from dataclasses import asdict, dataclass
from typing import Optional

from database.orm.orm import User


@dataclass
class BaseUser:
    username: str
    
    def is_valid(self):
        return self.username != ''
    
    def to_dict(self):
        return asdict(self)
    
@dataclass
class UserLogin(BaseUser):
    password: str
    
    def is_valid(self):
        return super().is_valid() and self.password != ''
    
    def to_dict(self):
        return asdict(self)
    
@dataclass
class UserInfo(BaseUser):
    balance: float
    
    def is_valid(self):
        return super().is_valid() and self.balance >= 0.0
    
    def to_dict(self):
        return asdict(self)
    
@dataclass
class UserDatabase(UserInfo):
    password: str
    salt: str
    
    def is_valid(self):
        return super().is_valid() and self.salt != '' and self.password != ''
    
    def to_dict(self):
        return asdict(self)

@dataclass(kw_only=True)
class Message:
    success: bool
    message: str
    data: Optional[dict] = None
    redirect: Optional[str] = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def success(cls, message: str = '', data: dict = None, redirect: str = None):
        return cls(success=True, message=message, data=data, redirect=redirect)

    @classmethod
    def failure(cls, message: str, redirect: str = None):
        return cls(success=False, message=message, redirect=redirect)
    
@dataclass
class Server:
    id: str
    ip: str
    port: int
    connected_users: int
    max_users: int
    key: str

    def get_url(self):
        return f'http://{self.ip}:{self.port}'

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(data):
        return Server(
            id=data["id"],
            ip=data["ip"],
            port=data["port"],
            connected_users=data["connected_users"],
            max_users=data["max_users"],
            key=data["key"] if "key" in data else None
        )
        
    @staticmethod
    def from_tuple(data):
        return Server(
            id=data[0],
            ip=data[1],
            port=data[2],
            connected_users=data[3],
            max_users=data[4],
            key=data[5] if len(data) > 5 else None
        )