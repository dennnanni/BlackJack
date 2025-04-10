class Table:
    def __init__(self):
        self.users = []
        self.game = None
    
    def add_user(self, user):
        self.users.append(user)
        
    def remove_user(self, user):
        self.users.remove(user)
        
    def has_users(self):
        return len(self.users) > 0
    
    def get_users(self):
        return self.users
    
    def start_game(self):
        if self.game is not None:
            raise Exception("Game already in progress")
        if not self.has_users():
            raise Exception("No users in the table")
        self.game = Game()
        return self.game
    
class Game:
    def __init__(self):
        pass
    
class User:
    def __init__(self):
        pass
    
class Deck:
    def __init__(self):
        pass
    
class Card:
    def __init__(self):
        pass
    
class Hand:
    def __init__(self):
        pass
    
class Result:
    def __init__(self):
        pass