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
    def __init__(self, players):
        self.__dealer_hand: list[Card] = []
        self.__active_users: list[User] = players
        self.__bets: dict[User, float] = {}
    
    def determine_result(self):
        results: list[Result] = []
        for user in self.__active_users:
            result = Result(user.get_username(), self.__determine_difference(user), user.get_balance())
                
    def __determine_difference(self, user):
        if self.__is_busted(user.get_hand()):
            return -self.__bets[user]
        elif self.__is_winner(user):
            return self.__bets[user]
        else:
            return 0
        
    def __is_winner(self, user):
        return self.__get_hand_value(self.__dealer_hand) < self.__get_hand_value(user.get_hand())
    
    def __get_hand_value(self, hand):
        return sum(card.get_value() for card in hand)
    
    def __is_busted(self, hand):
        return self.__get_hand_value(hand) > 21
        
    
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
    def __init__(self, username, balanceDifference, newBalance):
        self.username = username
        self.balanceDifference = balanceDifference
        self.newBalance = newBalance