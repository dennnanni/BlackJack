from dataclasses import asdict, dataclass


@dataclass
class User:
    username: str
    password: str
    salt: str
    balance: float
    
    def is_valid(self):
        return bool(self.username and self.password and self.salt and self.balance >= 0)
    
    def to_dict(self):
        return asdict(self)
        
        
@dataclass
class Message:
    success: bool
    message: str
    
    def to_dict(self):
        return asdict(self)