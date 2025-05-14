from dataclasses import asdict, dataclass


@dataclass
class User:
    username: str
    password: str
    salt: str
    balance: float = 0.0
    
    def is_valid(self):
        return self.username != '' and self.password != '' and self.salt != '' and self.balance >= 0
    
    def to_dict(self):
        return asdict(self)
        
@dataclass
class Message:
    success: bool
    message: str
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def success(cls, message: str):
        return cls(True, message)
    
    @classmethod
    def failure(cls, message: str):
        return cls(False, message)