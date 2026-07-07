"""The Blackjack game model: cards, hands, tables and rounds.

Pure in-memory logic with no I/O; everything real-time (sockets, timers,
result reporting) lives in the loop/events modules.
"""
import random

from shared.messages import Result


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

    def is_empty(self):
        return not self.__users and not self.__observers


class Game:

    DEALER_STAND_VALUE = 17

    def __init__(self, players, deck):
        self.__dealer_hand: list[Card] = []
        self.__active_users: list[User] = players
        self.__bets: dict[User, float] = {}
        self.__finished_users: list[User] = []
        self.__deck = deck

    def get_users(self):
        """Every user in the round, whether still acting or already done."""
        return self.__active_users + self.__finished_users

    def get_userbet(self, user):
        return self.__bets.get(user)

    def get_bet(self):
        return self.__bets

    def get_deck(self):
        return self.__deck

    def add_dealer_card(self, card):
        if Hand.is_busted(self.__dealer_hand) or Hand.is_blackjack(self.__dealer_hand) or Hand.get_hand_value(self.__dealer_hand) >= self.DEALER_STAND_VALUE:
            raise Exception("Dealer cannot take more cards")
        self.__dealer_hand.append(card)

    def place_bet(self, user, bet):
        """Registers a bet; returns True once every active user has bet."""
        if user not in self.__active_users:
            raise ValueError("User not in active users")
        if bet > user.get_balance():
            raise ValueError("Bet exceeds user's balance")
        self.__bets[user] = bet
        return self.all_players_have_bet()

    def all_players_have_bet(self):
        return len(self.__bets) == len(self.__active_users)

    def determine_result(self):
        results: list[Result] = []
        for user in self.get_users():
            if user not in self.__bets:
                continue
            diff = self._determine_difference(user)
            user.update_balance(diff)
            results.append(Result(user.get_username(), diff))
        return results

    def _determine_difference(self, user):
        if Hand.is_busted(user.get_hand()):
            return -self.__bets[user]
        if self._is_winner(user):
            return self.__bets[user]
        if self._is_push(user):
            return 0
        return -self.__bets[user]

    def _is_winner(self, user):
        if Hand.is_busted(user.get_hand()):
            return False
        if Hand.is_blackjack(user.get_hand()) and not Hand.is_blackjack(self.__dealer_hand):
            return True
        if Hand.is_busted(self.__dealer_hand):
            return True
        return Hand.get_hand_value(user.get_hand()) > Hand.get_hand_value(self.__dealer_hand)

    def _is_push(self, user):
        return (not Hand.is_busted(self.__dealer_hand)
                and Hand.get_hand_value(user.get_hand()) == Hand.get_hand_value(self.__dealer_hand))

    def player_double_down(self, user):
        self.place_bet(user, self.__bets[user] * 2)
        card = self.__deck.draw_card()
        user.add_card(card)
        self.remove_active_user(user)
        return card

    def player_stand(self, user):
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
        self.__username = username
        self.__balance = balance
        self.__cards = []

    def add_card(self, card):
        self.__cards.append(card)

    def remove_card(self, card):
        if card in self.__cards:
            self.__cards.remove(card)
        else:
            raise ValueError("Card not in user's hand")

    def clear_hand(self):
        self.__cards = []

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
        return self.value

    def __str__(self):
        return f"{self.type}{self.suit}"

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        if isinstance(other, Card):
            return self.type == other.type and self.suit == other.suit
        return False


class Hand:
    BLACKJACK = 21
    BLACKJACK_HAND_LENGTH = 2

    @staticmethod
    def get_hand_value(hand):
        # Aces count 11, then drop to 1 one at a time while the hand busts.
        hand_value = sum(card.get_value() for card in hand)
        aces = sum(1 for card in hand if card.get_value() == 11)
        while hand_value > Hand.BLACKJACK and aces:
            hand_value -= 10
            aces -= 1
        return hand_value

    @staticmethod
    def is_busted(hand):
        return Hand.get_hand_value(hand) > Hand.BLACKJACK

    @staticmethod
    def has_ace(hand):
        return any(card.get_value() == 11 for card in hand)

    @staticmethod
    def is_blackjack(hand):
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
                return table

        for table in self.__tables:
            if table.is_game_active():
                table.add_observer(user)
                self.__user_table_map[user.get_username()] = table
                return table

        new_table = Table(f"table_{len(self.__tables)+1}")
        new_table.add_user(user)
        self.__tables.append(new_table)
        self.__user_table_map[user.get_username()] = new_table
        return new_table

    def remove_user(self, user: User):
        table = self.__user_table_map.pop(user.get_username(), None)
        if table:
            table.remove_user(user)
        return table

    def get_user_table(self, username):
        return self.__user_table_map.get(username)

    def has_user(self, username):
        return username in self.__user_table_map
