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
    def __init__(self, username, balance):
        self.username = username  # Nome dell'utente
        self.balance = balance  # Saldo dell'utente (fiches o denaro)
        self.cards = []  # Mano dell'utente, inizialmente vuota
        self.is_connected = False 

    def add_card(self, card):
        """Aggiunge una carta alla mano dell'utente."""
        self.cards.append(card)
        
    def remove_card(self, card):
        """Rimuove una carta dalla mano del giocatore."""
        if card in self.cards:
            self.cards.remove(card)
        else:
            raise ValueError("Card not in user's hand")

    def get_hand(self):
        """Restituisce le carte attualmente nella mano dell'utente."""
        return self.cards

    def __str__(self):
        return f"User: {self.username}, Balance: {self.balance}, Hand: {self.get_hand()}"

    
class Deck:
    def __init__(self):
        pass
    
class Card:
    SUITS = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
    TYPES = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    VALUES = {
        'A': 11, #il valore uno dobbiamo
        '2': 2, '3': 3, '4': 4, '5': 5,
        '6': 6, '7': 7, '8': 8, '9': 9,
        '10': 10, 'J': 10, 'Q': 10, 'K': 10
    }
    
    def __init__(self, card_type, suit):
        if card_type not in self.TYPES:
            raise ValueError("Invalid card type")
        if suit not in range(4):
            raise ValueError("Invalid suit index")

        self.type = self.TYPES[card_type]
        self.suit = self.SUITS[suit]
        self.value = self.VALUES[card_type]
        
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
    def __init__(self):
        pass