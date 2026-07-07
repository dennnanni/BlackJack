# 03 — The Common Module

**Location:** `main_server/common/`
**Imported as:** `common` (e.g. `from common.structures import UserLogin`)

`common` is a **non-runnable shared library**. The three central services import from it so
that they agree on data shapes, response field names, and how to make HTTP calls. (The game
server has its *own* parallel copies of some of these structures — see the note at the end.)

It has three modules plus a small test.

---

## `common/structures.py` — shared data classes

Plain Python **`@dataclass`** definitions describing the entities passed around as JSON.
They form a small inheritance hierarchy for users:

```
BaseUser(username)
 ├── UserLogin(+ password)
 └── UserInfo(+ balance)
      └── UserDatabase(+ password, salt)     # the full DB record
```

| Class | Fields | Used for |
|---|---|---|
| `BaseUser` | `username` | base; `is_valid()` checks username non-empty |
| `UserLogin` | `username, password` | login request payload (password already hashed) |
| `UserInfo` | `username, balance` | what the UI shows about a user |
| `UserDatabase` | `username, balance, password, salt` | full user row (register payload / DB read) |

Each has:
- `is_valid()` — cheap validation (non-empty fields, `balance >= 0`), chained via `super()`.
- `to_dict()` — `dataclasses.asdict(self)` so it can be JSON-serialized.

### Server-related structures

```
Server(ip, port, key)
 └── RegisteredServer(+ id)
      └── ServerLoad(+ connected_users, max_users)
```

| Class | Notable methods |
|---|---|
| `Server` | `get_url()` → `http://{ip}:{port}`; `to_dict()`; `from_dict()` |
| `RegisteredServer` | adds `id`; its own `from_dict()` |
| `ServerLoad` | adds `connected_users`, `max_users`; `from_dict()` **and** `from_tuple()` |

`ServerLoad.from_tuple()` exists because `database_interface` builds this object from a raw
SQL query result row (a tuple of `(id, ip, port, connected_users, max_users, key)`), where
`key` is optional. `from_dict()` is used on the client side to rebuild it from JSON.

### `Result`

```python
@dataclass
class Result:
    username: str
    balance_difference: float
```

Represents the outcome of one player in one round (positive = won, negative = lost). This is
the unit that flows from a game server all the way back to the database to update balances.

> ⚠️ The game server has its **own** `Result` dataclass in
> `game_server/src/model/game_structures.py`, and that copy has a bug (`to_dict()` is missing
> a `return`). See [doc 12](12-known-issues.md). The `common` one here is correct.

> 🐞 Minor: line 2 of this file has a stray `from turtle import st` import (an editor
> autocomplete accident). It's unused and harmless but should be removed.

---

## `common/response_fields.py` — string constants

A flat list of the **string keys** used in JSON request/response bodies, centralized so the
producer and consumer never disagree on spelling:

```python
SUCCESS = 'success'   ERROR = 'error'       TOKEN = 'token'
SALT = 'salt'         REDIRECT = 'redirect' DATA = 'data'
ENCRYPTED = 'encrypted'  SERVER_ID = 'server_id'  PLAYING = 'playing'
```

Convention throughout the codebase:
- **Success** responses carry `success=True` (or a `data` payload).
- **Error** responses carry an `error` string.

Code typically checks `response.get(ERROR)` to detect failure, since the HTTP helper returns
a dict either way (see below).

---

## `common/http_requests.py` — the service-to-service HTTP helper

A thin wrapper over **`requests`** used for **all central-service-to-central-service** calls.

```python
make_request(method, url, endpoint, *, params, json_data, headers)
get_request(url, endpoint, params=None)
post_request(url, endpoint, json_data)
```

Behavior worth knowing:
- It builds the full URL as `f'{url}/{endpoint}'`.
- Timeout is hard-coded to **5 seconds**.
- It **always returns the parsed JSON dict** (never raises for HTTP errors). On a transport
  failure or invalid JSON it returns `{ERROR: '...'}`. This is why callers everywhere do
  `if response.get(ERROR): ...` rather than try/except.

Example, from `client_interface`'s dispatcher:
```python
response = get_request(DATABASE_URL, GAME_SERVERS_API_ENDPOINT)
if response.get(ERROR):
    return None, response.get(ERROR)
servers = response.get(DATA)
```

> Note: the game server does **not** use this helper. It has its own HTTP/crypto client in
> `game_server/src/central_api.py` because its calls are encrypted (see [doc 08](08-game-server.md)).

---

## `common/test/test_structures.py`

A single pytest that confirms `UserDatabase.is_valid()` returns `True` for a well-formed user
and `False` when the username is empty. Run with `pytest main_server/common`.

---

## Important: the game server duplicates some of this

The game server is meant to be independently deployable, so it does **not** import `common`.
Instead, `game_server/src/model/game_structures.py` re-declares its own `Result` (and has
richer game-only classes like `Card`, `Deck`, `Hand`, `Game`, `Table`, `User`,
`TableManager`). If you change the shape of `Result` in `common`, remember the game server
has a parallel definition that must be kept in sync.

Next: [04 — Data Model & Database](04-data-model.md).
