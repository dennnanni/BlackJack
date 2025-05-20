from dataclasses import dataclass
from common.structures import BaseUser
from flask_login import UserMixin

@dataclass
class UserSession(BaseUser, UserMixin):
    
    def get_id(self):
        return self.username