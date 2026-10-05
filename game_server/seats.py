"""Who is seated at which table, and the operations that seat and unseat
players."""
import time

from game_server.game.model import TableManager
from game_server.runtime import BOOT_ID, closing, outbox, socketio

table_manager = TableManager()
user_map = {}
table_game_map = {}

# Players who asked to skip rounds
sitting_out = set()

# Ids of buy-ins that already seated a player.
seated_buy_ins = set()

# Players who went away keep their seat until the end of the
# round and are unseated then if they never came back
absent = {}


def seated_players():
    """Usernames seated here. Central reads it as our load and as the renewal
    of these players' seat leases."""
    return list(user_map)


def tables_idle():
    """Nobody seated and no table in the middle of a round."""
    return not user_map and not any(loop.running for loop in table_game_map.values())


def room(table):
    return f"table-{table.id}"


def can_take_seat(buy_in_id, join_exp, boot_id):
    return (buy_in_id is not None and buy_in_id not in seated_buy_ins
            and boot_id == BOOT_ID
            and time.time() <= join_exp
            and not closing.is_set())


def unseat(username, close_buy_in=True):
    """Remove a player from their table and have central close their buy-in,
    handing what is left of it back to their balance."""
    user = user_map.pop(username, None)
    if user is None:
        return
    table_manager.remove_user(user)
    absent.pop(username, None)
    sitting_out.discard(username)
    if close_buy_in and user.buy_in_id:
        outbox.enqueue_leave(user.buy_in_id)


def leave_table(username):
    """A player pressed "Leave table"."""
    user = user_map.get(username)
    if user is None:
        return
    table = table_manager.get_user_table(username)
    game = table.game if table else None
    
    
    # If the player has a bet in play, their buy-in is closed only after the
    # round's result. Otherwise central would give the bet back before charging the loss.
    stake_in_play = game is not None and user in game.bets
    if game and user in game.get_users():
        game.forfeit(user)
        game_loop = table_game_map.get(table.id)
        if game_loop and game_loop.current_player is user:
            game_loop.turn_done_event.set()   # don't hold the table for them
        socketio.emit('player_left', {'user': username}, to=room(table))
    unseat(username, close_buy_in=not stake_in_play)


def close_forfeited_buy_ins(game):
    """Called by the loop when a round is over, after its results are in the
    outbox: close the buy-ins leave_table kept open for a stake in play."""
    for user in game.forfeited:
        if user in game.bets and user.buy_in_id:
            outbox.enqueue_leave(user.buy_in_id)


def reap_absent(table):
    """Called by the loop between rounds: unseat the players of this table
    whose socket never came back."""
    for username in [u for u in list(absent) if table_manager.get_user_table(u) is table]:
        unseat(username)
