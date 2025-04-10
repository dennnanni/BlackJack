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
            results.append(result)
        return results
                
    def __determine_difference(self, user):
        if Hand.__is_busted(user.get_hand()):
            return -self.__bets[user]
        elif self.__is_winner(user):
            return self.__bets[user]
        else:
            return 0
        
    def __is_winner(self, user):
        """Controlla se l'utente ha vinto la mano, non considera il pareggio."""
        return not Hand.__is_busted(user.get_hand()) and \
            Hand.__get_hand_value(self.__dealer_hand) < Hand.__get_hand_value(user.get_hand()) or \
            Hand.__is_blackjack(user.get_hand()) and not Hand.__is_blackjack(self.__dealer_hand)
    
class User:
    def __init__(self, username, balance):
        self.__username = username  # Nome dell'utente
        self.__balance = balance  # Saldo dell'utente (fiches o denaro)
        self.__cards = []  # Mano dell'utente, inizialmente vuota
        self.is_connected = False 

    def add_card(self, card):
        self.__cards.append(card)
        
    def remove_card(self, card):
        """Rimuove una carta dalla mano del giocatore."""
        if card in self.__cards:
            self.__cards.remove(card)
        else:
            raise ValueError("Card not in user's hand")
        
    def get_username(self):
        return self.__username

    def get_balance(self):
        return self.__balance

    def get_hand(self):
        return self.__cards

    def __str__(self):
        return f"User: {self.__username}, Balance: {self.__balance}, Hand: {self.__cards}"

    
class Deck:
    def __init__(self):
        pass
    
class Card:
    SUITS = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
    TYPES = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    VALUES = {
        'A': 11,
        '2': 2, '3': 3, '4': 4, '5': 5,
        '6': 6, '7': 7, '8': 8, '9': 9,
        '10': 10, 'J': 10, 'Q': 10, 'K': 10
    }
    
    def __init__(self, card_type, suit):
        if card_type not in range(len(self.TYPES)):
            raise ValueError("Invalid card type")
        if suit not in range(4):
            raise ValueError("Invalid suit index")

        self.type = self.TYPES[card_type]
        self.suit = self.SUITS[suit]
        self.value = self.VALUES[self.type]
        
    def get_value(self):
        """Restituisce il valore della carta."""
        return self.value

    def __str__(self):
        return f"{self.type}{self.suit}"

    def __repr__(self):
        return self.__str__()
    
    def __eq__(self, other):
        """Confronta se due carte sono uguali in base a tipo e seme."""
        if isinstance(other, Card):
            return self.type == other.type and self.suit == other.suit
        return False
    
class Result:
    def __init__(self, username, balanceDifference, newBalance):
        self.username = username
        self.balanceDifference = balanceDifference
        self.newBalance = newBalance
        
class Hand:
    BLACKJACK = 21
    BLACKJACK_HAND_LENGTH = 2
    
    @staticmethod
    def get_hand_value(hand):
        hand_value = sum(card.get_value() for card in hand)
        if Hand.has_ace(hand) and hand_value > Hand.BLACKJACK:
            # Se la mano ha un asso e il valore supera 21, sottraiamo 10
            hand_value -= 10
        return hand_value
    
    @staticmethod
    def is_busted(hand):
        return Hand.get_hand_value(hand) > Hand.BLACKJACK
    
    @staticmethod
    def has_ace(hand):
        return any(card.get_value() == 11 for card in hand)
    
    @staticmethod
    def is_blackjack(hand):
        """Controlla se la mano è un blackjack (21 con due carte)."""
        return len(hand) == Hand.BLACKJACK_HAND_LENGTH and Hand.get_hand_value(hand) == Hand.BLACKJACK and Hand.has_ace(hand)
        