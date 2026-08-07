"""The Blackjack game model: cards, hands, tables and rounds.

Pure in-memory logic with no I/O; everything real-time (sockets, timers,
result reporting) lives in the loop/events modules.
"""
import random
from itertools import product

from shared.messages import Result


class Table:
    MAX_USER_IN_TABLE = 3

    def __init__(self, id):
        self.id = id
        self.users = []
        self.observers = []
        self.game = None

    def add_user(self, user):
        self.users.append(user)

    def add_observer(self, user):
        self.observers.append(user)

    def remove_user(self, user):
        if user in self.users:
            self.users.remove(user)
        elif user in self.observers:
            self.observers.remove(user)

    def is_game_active(self):
        return self.game is not None

    def is_ready_to_start(self):
        return len(self.users) > 0 and self.game is None

    def clear_game(self):
        self.users += self.observers
        self.observers = []
        self.game = None

    def table_is_not_full(self):
        return len(self.users + self.observers) < self.MAX_USER_IN_TABLE


class Game:

    DEALER_STAND_VALUE = 17

    def __init__(self, players, deck):
        self.dealer_hand: list[Card] = []
        self.active_users: list[User] = players
        self.bets: dict[User, float] = {}
        self.finished_users: list[User] = []
        self.deck = deck

    def get_users(self):
        """Every user in the round, whether still acting or already done."""
        return self.active_users + self.finished_users

    def add_dealer_card(self, card):
        if Hand.is_busted(self.dealer_hand) or Hand.is_blackjack(self.dealer_hand) or Hand.get_hand_value(self.dealer_hand) >= self.DEALER_STAND_VALUE:
            raise Exception("Dealer cannot take more cards")
        self.dealer_hand.append(card)

    def place_bet(self, user, bet):
        """Registers a bet; returns True once every active user has bet."""
        if user not in self.active_users:
            raise ValueError("User not in active users")
        if bet > user.balance:
            raise ValueError("Bet exceeds user's balance")
        self.bets[user] = bet
        return self.all_players_have_bet()

    def all_players_have_bet(self):
        return len(self.bets) == len(self.active_users)

    def determine_result(self):
        results: list[Result] = []
        for user in self.get_users():
            if user not in self.bets:
                continue
            diff = self._determine_difference(user)
            user.update_balance(diff)
            results.append(Result(user.username, diff))
        return results

    def _determine_difference(self, user):
        if Hand.is_busted(user.hand):
            return -self.bets[user]
        if self._is_winner(user):
            return self.bets[user]
        if self._is_push(user):
            return 0
        return -self.bets[user]

    def _is_winner(self, user):
        if Hand.is_busted(user.hand):
            return False
        if Hand.is_blackjack(user.hand) and not Hand.is_blackjack(self.dealer_hand):
            return True
        if Hand.is_busted(self.dealer_hand):
            return True
        return Hand.get_hand_value(user.hand) > Hand.get_hand_value(self.dealer_hand)

    def _is_push(self, user):
        return (not Hand.is_busted(self.dealer_hand)
                and Hand.get_hand_value(user.hand) == Hand.get_hand_value(self.dealer_hand))

    def player_double_down(self, user):
        if user not in self.bets:
            raise ValueError("Cannot double down without a bet")
        if len(user.hand) != Hand.BLACKJACK_HAND_LENGTH:
            raise ValueError("Can only double down on the first two cards")
        self.place_bet(user, self.bets[user] * 2)
        card = self.deck.draw_card()
        user.add_card(card)
        self.remove_active_user(user)
        return card

    def player_stand(self, user):
        self.remove_active_user(user)

    def remove_active_user(self, user):
        if user in self.active_users:
            self.active_users.remove(user)
            self.finished_users.append(user)

    def restore_active_user(self, user):
        """Put a user back in the round — only meaningful before the deal
        (a player who sat out and changed their mind during the betting
        window)."""
        if user in self.finished_users:
            self.finished_users.remove(user)
            self.active_users.append(user)


class User:
    def __init__(self, username, balance):
        self.username = username
        self.balance = balance
        self.hand = []

    def add_card(self, card):
        self.hand.append(card)

    def clear_hand(self):
        self.hand = []

    def update_balance(self, amount):
        self.balance += amount

    def __str__(self):
        return f"User: {self.username}, Balance: {self.balance}, Hand: {self.hand}"


class Deck:
    def __init__(self):
        self.cards = [Card(card_type, suit)
                      for card_type, suit in product(Card.TYPES, Card.SUITS)]
        random.shuffle(self.cards)

    def draw_card(self):
        if not self.cards:
            raise Exception("No cards left in the deck")
        return self.cards.pop()


class Card:
    SUITS = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
    SUIT_SYMBOLS = ['♥', '♦', '♣', '♠']
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

    def __str__(self):
        return f"{self.type}{self.SUIT_SYMBOLS[self.suit]}"

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
        hand_value = sum(card.value for card in hand)
        aces = sum(1 for card in hand if card.value == 11)
        while hand_value > Hand.BLACKJACK and aces:
            hand_value -= 10
            aces -= 1
        return hand_value

    @staticmethod
    def is_busted(hand):
        return Hand.get_hand_value(hand) > Hand.BLACKJACK

    @staticmethod
    def has_ace(hand):
        return any(card.value == 11 for card in hand)

    @staticmethod
    def is_blackjack(hand):
        return len(hand) == Hand.BLACKJACK_HAND_LENGTH and Hand.get_hand_value(hand) == Hand.BLACKJACK and Hand.has_ace(hand)


class TableManager:

    def __init__(self):
        self.tables: list[Table] = []
        self.user_table_map: dict[str, Table] = {}

    def assign_user_to_table(self, user: User):
        for table in self.tables:
            if table.table_is_not_full() and not table.is_game_active():
                table.add_user(user)
                self.user_table_map[user.username] = table
                return table

        for table in self.tables:
            if table.is_game_active():
                table.add_observer(user)
                self.user_table_map[user.username] = table
                return table

        new_table = Table(f"table_{len(self.tables)+1}")
        new_table.add_user(user)
        self.tables.append(new_table)
        self.user_table_map[user.username] = new_table
        return new_table

    def remove_user(self, user: User):
        table = self.user_table_map.pop(user.username, None)
        if table:
            table.remove_user(user)
        return table

    def get_user_table(self, username):
        return self.user_table_map.get(username)

    def has_user(self, username):
        return username in self.user_table_map
