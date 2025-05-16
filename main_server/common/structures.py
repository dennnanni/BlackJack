from dataclasses import asdict, dataclass

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
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def success(cls, message: str):
        return cls(message=message, success=True)
    
    @classmethod
    def failure(cls, message: str):
        return cls(message=message, success=False)

@dataclass(kw_only=True)
class DataMessage(Message):
    data: dict
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def success(cls, message: str, data: dict):
        return cls(message=message, success=True, data=data)
    
    @classmethod
    def failure(cls, message: str, data: dict):
        return cls(message=message, success=False, data=data)
    

@dataclass(kw_only=True)
class RedirectionMessage(Message):
    redirect: str
    
    @classmethod
    def success(cls, message: str, redirect: str):
        return cls(message=message, success=True, redirect=redirect)
    
    @classmethod
    def failure(cls, message: str, redirect: str):
        return cls(message=message, success=False, redirect=redirect)