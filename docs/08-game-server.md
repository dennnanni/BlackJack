# 08 — The Game Server

**Path:** `game_server/`
**Package:** `src` (imports look like `from src.model.game_structures import ...`)
**Run with:** `poetry run game_server`
**Port:** `8000` (default `SERVER_PORT`, configurable)
**Role:** A **standalone, replicable** process that runs the real-time Blackjack game. It
authenticates joining players via JWT, manages tables, runs each round through a state
machine in a background thread, and pushes live updates to browsers via Socket.IO. When a
round ends it reports balance changes upstream.

This is the largest and most interesting part of the codebase. Take your time here.

## File map

```
game_server/
├── src/
│   ├── __init__.py        # create_app(): generates this server's Fernet key, registers with central
│   ├── main.py            # entry point: socketio.run(app, port=SERVER_PORT)
│   ├── config/
│   │   └── settings.py    # env-driven config (host, port, central URL, shared secret)
│   ├── central_api.py     # HTTP client to the central server (register / results / users)
│   ├── encryption.py      # encrypt_with_key / decrypt_with_key (Fernet helpers)
│   ├── routes.py          # registers the HTTP blueprint
│   ├── controller/
│   │   └── connection_controller.py   # GET / (index) and POST /join (JWT-gated)
│   ├── event_handlers.py  # Socket.IO game events: join / bet / player_action
│   ├── game_loop.py       # GameLoop: the per-table round state machine (a Thread)
│   ├── model/
│   │   └── game_structures.py  # Card, Deck, Hand, User, Game, Table, TableManager, Result
│   └── templates/
│       └── index.html     # game UI (currently a stub; real UI commented out)
└── tests/                 # pytest suite for the game model (the best-tested code in the repo)
```

## Startup sequence (`__init__.py`)

This is where the game server announces itself to the world:

```python
socketio = SocketIO(cors_allowed_origins="*")
key = Fernet.generate_key()                       # THIS server's unique key
central_client = CentralServerAPI(CENTRAL_SERVER_URL)

def create_app():
    app = Flask(__name__)
    register_routes(app)
    socketio.init_app(app)

    # Try up to 5 times to register with central, 2s apart; exit(1) if all fail.
    for i in range(5):
        if central_client.register_game_server(host, port, shared_key=SHARED_SECRET, new_key=key):
            break
        time.sleep(2)
    else:
        exit(1)

    register_event_handlers(socketio)
    return app
```

Key facts:
- `key` is a **module-level Fernet key generated fresh on every boot.** It is this server's
  identity for signing/verifying JWTs. (It is *also* used directly as the JWT
  verification secret in `/join` — see below.)
- Registration is **retried** (the commit history shows this was added deliberately to handle
  the central server not being up yet). If it can't register, the process **exits** — a game
  server that central doesn't know about is useless.
- Three module-level singletons matter for the whole server: `socketio`, `key`,
  `central_client`.

## Configuration (`config/settings.py`)

| Variable | Default | Meaning |
|---|---|---|
| `SERVER_HOST` | `127.0.0.1` | IP advertised to central during registration |
| `SERVER_PORT` | `5000` | port the game server listens on (Docker sets `8000`) |
| `CENTRAL_SERVER_URL` | `http://localhost:5002` | the `servers_interface` URL |
| `SHARED_SECRET` | (required) | the global Fernet secret; raises if missing |

## The central client (`central_api.py`)

`CentralServerAPI` wraps the three upstream calls. It uses the Fernet helpers in
`encryption.py`.

| Method | Calls | Payload | Status |
|---|---|---|---|
| `register_game_server(host, port, shared_key, new_key)` | `POST /register` | `{"encrypted": Fernet(shared_key).encrypt({ip,port,key})}` | ✅ working; stores returned `server_id` |
| `send_results(results)` | `POST /results` | `{"data": Fernet(new_key).encrypt({"results":[...]})}` | ⚠️ **mismatched** with the server (see below) |
| `update_user_list(users)` | `POST /users` | `{"data": Fernet(new_key).encrypt({server_id, users})}` | ⚠️ **no such endpoint** on central |

**Registration** is the clean, working path: encrypt `{ip,port,key}` with the shared secret,
POST it, then decrypt the response (encrypted with *our* key) to learn our `server_id`.

**`send_results` / `update_user_list` are inconsistent** with `servers_interface` as it exists
today: `servers_interface` `/results` expects a **JWT** in `{"token": ...}` plus an
`X-Server-ID` header, and has **no** `/users` route at all. So these two methods don't
currently succeed end-to-end. Treat them as unfinished. (See [doc 12](12-known-issues.md).)

## The HTTP entry: joining (`controller/connection_controller.py`)

| Method & path | Purpose |
|---|---|
| `GET /` | Render `index.html` (the game page — currently a stub). |
| `POST /join` | Validate the player's JWT and admit them. |

`/join` reads `token` from the form, then `jwt.decode(token, key, algorithms=['HS256'])` using
**this server's own `key`**. This is the security pivot: `client_interface` minted that JWT
using the very same key (it got it by decrypting the server's stored key with the shared
secret). A valid decode proves the player was legitimately dispatched here. On success it
returns `{status:'ok', username}`; on failure `401`.

> The intended flow after `/join` is for the browser to open a Socket.IO connection and emit
> `join`. Because the real game UI in `index.html` is commented out, this last hop isn't wired
> up in the shipped template (see doc 12).

## The real-time game (`event_handlers.py`)

Three module-level singletons hold all live state (in-memory, per process):

```python
table_manager  = TableManager()   # assigns users to tables
user_map       = {}               # username -> User (game model object)
table_game_map = {}               # table_id -> GameLoop (the running thread)
```

### `join` event
1. Build a `User(username, balance)`, store in `user_map`.
2. `table_manager.assign_user_to_table(user)` → a `Table`. Join the Socket.IO **room**
   `table-<id>`.
3. If the table `is_ready_to_start()` and no loop is running for it, create and `start()` a
   `GameLoop` (a thread) and remember it in `table_game_map`. Emit `joined` with `is_player`.
4. If a game is already in progress, send the joiner the current `initial_cards` snapshot
   (they're an observer until next round).
5. `central_client.update_user_list(...)` (the call that currently doesn't land — see above).

### `bet` event
- Validates the user is at a table with an active game, then `game.place_bet(user, amount)`.
- Signals the running loop via `bets_done_event.set()` when bets are in.

### `player_action` event (`hit` / `stand` / `double`)
- `hit`: draw a card, add to hand, emit `card_drawn`; if busted, remove from active users and
  emit `player_busted`.
- `stand`: remove from active users, emit `user_stood`.
- `double`: `game.player_double_down(user)` (doubles the bet, draws one card, ends their turn),
  emit `user_doubled`.
- When `all_players_done()`, set `actions_done_event` so the loop advances to the dealer phase.

## The round state machine (`game_loop.py`)

`GameLoop(Thread)` runs one table's rounds. It coordinates with the event handlers through two
`threading.Event`s: `bets_done_event` and `actions_done_event`. Its `run()` loops as long as
the table `is_ready_to_start()`:

```
┌─ game_starting ──────────────────────────────────────────────┐
│ 1. new Deck + new Game; attach to table                       │
│ 2. emit place_bets;  wait up to 35s for bets_done_event       │
│    └─ players with no bet are removed; if nobody bet →         │
│       emit no_players_bet, clear game, stop.                  │
│ 3. deal two cards to each active player                        │
│ 4. emit initial_cards                                          │
│ 5. wait up to 60s for actions_done_event (players hit/stand)   │
│ 6. anyone who didn't act → auto-stand (emit player_auto_stand) │
│ 7. dealer draws until hand value ≥ 17 (DEALER_STAND_VALUE)     │
│ 8. emit dealer_done                                            │
│ 9. determine_result() → emit round_results                     │
│10. central_client.send_results(results)                        │
│11. clear game + reset the two Events, loop back to step 1      │
└───────────────────────────────────────────────────────────────┘
```

Timeouts are real wall-clock waits (`Event.wait(timeout=...)`), so a table progresses even if
players go idle. The comment says "15 seconds" but the code actually waits 60 for actions and
35 for bets — trust the code.

## The domain model (`model/game_structures.py`)

This file is pure game logic, no Flask, and is the **best-tested** module in the project. The
classes:

### `Card`
- `SUITS = [Hearts, Diamonds, Clubs, Spades]`, `TYPES = A,2..10,J,Q,K`.
- `VALUES`: face cards = 10, **Ace = 11** (soft-ace adjustment happens in `Hand`).
- `__str__` is `f"{type}{suit_index}"` (e.g. `"A0"` = Ace of Hearts). Equality compares
  type + suit.

### `Deck`
- Builds one card per (suit, type) → 52 cards for `num_decks=1`.
- `draw_card()` pops a **random** index (so no shuffling needed; drawing is the randomness).
  Raises if empty.

### `Hand` (all static methods — operates on a list of cards)
- `get_hand_value(hand)`: sum of values; if there's an ace and total > 21, subtract 10
  (treats one ace as 1 instead of 11). *Note: only adjusts for a single ace.*
- `is_busted` (> 21), `has_ace`, `is_blackjack` (exactly 2 cards, value 21, contains an ace).

### `User` (the in-game player; distinct from the DB user)
- Holds `username`, `balance`, and the current `cards` hand. `add_card` / `remove_card` /
  `update_balance` / getters.

### `Game` (one round)
- Tracks `dealer_hand`, `active_users`, `bets` (dict User→amount), `finished_users`, the `deck`.
- `place_bet` (validates balance, can't bet more than balance), `player_double_down`,
  `remove_active_user`, `add_dealer_card` (refuses once dealer is at/over 17 or done).
- `determine_result()` → for each player computes `_determine_difference`:
  - busted → lose the bet (`-bet`);
  - winner (blackjack beats non-blackjack, or higher value than dealer) → win the bet (`+bet`);
  - otherwise → `0`.
  It also applies the diff to the in-memory `User.balance` and returns a list of `Result`.
- `DEALER_STAND_VALUE = 17`.

> Payout model is **even money / push-or-lose-bet**: a win returns `+bet`, a loss returns
> `-bet`, ties return `0`. There's no 3:2 blackjack bonus and no separate "push" handling
> beyond returning 0.

### `Table`
- Holds `users` (players) and `observers` (people who joined mid-game), an `id`, and the
  current `game`.
- `MAX_USER_IN_TABLE = 3`. `is_ready_to_start()` = has ≥1 user and no active game.
  `clear_game()` promotes observers to players and detaches the game (ready for next round).

### `TableManager`
- `assign_user_to_table(user)`: put the user in the first non-full table without an active
  game; else attach as observer to a table that's mid-game; else create a new `Table`.
  `MAX_NUMBER_OF_TABLE = 3` exists as a constant but isn't enforced in the assignment logic.
- `get_user_table(username)`, `has_user(username)`.

### `Result` (game server's own copy)
- `username` + `balance_difference`. ⚠️ Its `to_dict()` is missing a `return` (returns `None`).
  See doc 12. (`game_loop.py` actually serializes results with `vars(r)` for the socket emit,
  sidestepping that bug for the UI path.)

## Tests (`game_server/tests/`)

The richest test suite in the repo, covering the model:
- `test_card_and_deck.py` — card values, deck size after a draw.
- `test_hand.py` / `test_game_logic.py` — hand values (incl. ace logic), blackjack, bust,
  winner determination, bet-exceeds-balance error, dealer-stop rule, double-down/difference math.
- `test_game.py` — a full bet→deal→result flow updating balance.
- `test_user.py` — user creation, hand mutation, balance update.
- `test_tablemanager.py` — table assignment/grouping across many users.

Run them with `pytest game_server` (this is what `.vscode/settings.json` is configured for).

Next: [09 — Security & Encryption](09-security.md).
