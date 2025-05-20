import random

class Table:
    MAX_USER_IN_TABLE = 3

    def __init__(self, id):
        self.__users = []
        self.__observers = []
        self.__id = id
        self.__game = None

    def add_user(self, user):
        self.__users.append(user)

    def add_observer(self, user):
        self.__observers.append(user)
        
    def all_players_have_bet(self):
        return self.__game.get_bet() == self.__users

    def remove_user(self, user):
        if user in self.__users:
            self.__users.remove(user)
        elif user in self.__observers:
            self.__observers.remove(user)

    def has_user(self, username):
        return any(u.get_username() == username for u in self.__users + self.__observers)

    def is_game_active(self):
        return self.__game is not None

    def is_ready_to_start(self):
        return len(self.__users) > 0 and self.__game is None

    def get_table_id(self):
        return self.__id
    
    def get_users(self):
        return self.__users
    
    def set_game(self, game):
        self.__game = game
        
    def get_game(self):
        return self.__game

    def clear_game(self):
        for u in self.__observers:
            self.add_user(u)
        self.__observers = []
        self.__game = None

    def table_is_not_full(self):
        return len(self.__users + self.__observers) < self.MAX_USER_IN_TABLE

class Game:
    
    DEALER_STAND_VALUE = 17
    
    def __init__(self, players, deck):
        self.__dealer_hand: list[Card] = []
        self.__active_users: list[User] = players
        self.__bets: dict[User, float] = {}
        self.__finished_users: list[User] = []
        self.__deck = deck
        
    def get_users(self):
        """Restituisce la lista degli utenti attivi."""
        return self.__active_users
    
    def get_bet(self, user):
        return self.__bets.get(user)

    def get_deck(self):
        return self.__deck
    
    def add_dealer_card(self, card):
        """Aggiunge una carta alla mano del dealer."""
        if Hand.is_busted(self.__dealer_hand) or Hand.is_blackjack(self.__dealer_hand) or Hand.get_hand_value(self.__dealer_hand) >= self.DEALER_STAND_VALUE:
            raise Exception("Dealer cannot take more cards")
        self.__dealer_hand.append(card)
        
    def place_bet(self, user, bet):
        """Pone una scommessa per l'utente."""
        if user not in self.__active_users:
            raise ValueError("User not in active users")
        if bet > user.get_balance():
            raise ValueError("Bet exceeds user's balance")
        self.__bets[user] = bet
        return len(self.__bets) == len(self.__active_users)
    
    def determine_result(self):
        results: list[Result] = []
        for user in self.__active_users:
            diff = self._determine_difference(user)
            user.update_balance(diff)
            result = Result(user.get_username(), diff, user.get_balance())
            results.append(result)
        return results
                
    def _determine_difference(self, user):
        if Hand.is_busted(user.get_hand()):
            return -self.__bets[user]
        elif self._is_winner(user):
            return self.__bets[user]
        else:
            return 0
        
    def _is_winner(self, user):
        """Controlla se l'utente ha vinto la mano, non considera il pareggio."""
        return not Hand.is_busted(user.get_hand()) and \
            Hand.get_hand_value(self.__dealer_hand) < Hand.get_hand_value(user.get_hand()) or \
            Hand.is_blackjack(user.get_hand()) and not Hand.is_blackjack(self.__dealer_hand)

    def player_double_down(self, user):
        self.place_bet(user, self.__bets[user] * 2)
        user.add_card(self.__deck.draw_card())
        self.remove_active_user(user)
    
    def remove_active_user(self, user):
        if user in self.__active_users:
            self.__active_users.remove(user)
            self.__finished_users.append(user)
            
    def get_active_users(self):
        return self.__active_users

    def get_dealer_hand(self):
        return self.__dealer_hand

    def all_players_done(self):
        return len(self.__active_users) == 0
    
class User:
    def __init__(self, username, balance):
        self.__username = username  # Nome dell'utente
        self.__balance = balance  # Saldo dell'utente (fiches o denaro)
        self.__cards = []  # Mano dell'utente, inizialmente vuota

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
    
    def update_balance(self, amount):
        self.__balance += amount
    
class Deck:
    def __init__(self, num_decks=1):
        self.cards = []
        # Builds the deck with the specified number of decks
        for suit in Card.SUITS:
            for card_type in Card.TYPES:
                for _ in range(num_decks):
                    self.cards.append(Card(card_type, suit))
    
    def draw_card(self):
        """Pesca una carta dal mazzo."""
        if not self.cards:
            raise Exception("No cards left in the deck")
        card_index = random.randint(0, len(self.cards) - 1)
        return self.cards.pop(card_index)
    
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
        if card_type.upper() not in self.TYPES:
            raise ValueError("Invalid card type")
        if suit.capitalize() not in self.SUITS:
            raise ValueError("Invalid suit")

        self.type = card_type.upper()
        self.suit = self.SUITS.index(suit.capitalize())
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
        
class TableManager:
    
    MAX_NUMBER_OF_TABLE = 3
    
    def __init__(self):
        self.__tables: list[Table] = []
        self.__user_table_map: dict[str, Table] = {}

    def assign_user_to_table(self, user: User):
        for table in self.__tables:
            if table.table_is_not_full() and not table.is_game_active():
                table.add_user(user)
                self.__user_table_map[user.get_username()] = table
                return table, True

        
        for table in self.__tables:
            if table.is_game_active() and not table.has_user(user.get_username()):
                table.add_observer(user)
                self.__user_table_map[user.get_username()] = table
                return table, True 

        new_table = Table(f"table_{len(self.__tables)+1}")
        new_table.add_user(user)
        self.__tables.append(new_table)
        self.__user_table_map[user.get_username()] = new_table
        return new_table, True

    def get_user_table(self, username):
        return self.__user_table_map.get(username)

    def has_user(self, username):
        return username in self.__user_table_map

