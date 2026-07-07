# 04 — Data Model & Database

The database is **PostgreSQL**. It has exactly **three tables**. They are defined in two
places that must agree:

1. **`database/db_create.sql`** — raw SQL, kept as a reference / manual bootstrap script.
2. **`main_server/database_interface/database/orm/orm.py`** — the SQLAlchemy ORM models,
   which are what the running app actually uses.

At import time, `database_actions.py` calls `Base.metadata.create_all(bind=engine)`, so the
ORM **auto-creates** any missing tables when `database_interface` starts. You don't strictly
need to run the SQL file yourself.

## The three tables

### `user` — player accounts

| Column | SQL type | ORM | Notes |
|---|---|---|---|
| `username` | `TEXT PRIMARY KEY` | `String, primary_key` | the unique handle / login id |
| `password` | `TEXT NOT NULL` | `String, nullable=False` | **PBKDF2-HMAC-SHA256 hash**, base64 (never plaintext) |
| `salt` | `TEXT NOT NULL` | `String, nullable=False` | per-user base64 salt used to derive the hash |
| `balance` | `NUMERIC(10,2) DEFAULT 0.0` | `Numeric(10,2), default=0.0` | the player's money/chips |

> The username is the primary key — there is no separate numeric user id.
> New users start with a balance of **1000** (`INITIAL_BALANCE` in `client_interface/constants.py`),
> not 0; the DB default of 0 only applies if a row is inserted without a balance.

### `gameserver` — registry of running game servers

| Column | SQL type | ORM | Notes |
|---|---|---|---|
| `id` | `SERIAL PRIMARY KEY` | `Integer, primary_key, autoincrement` | assigned on registration |
| `ip` | `TEXT NOT NULL` | `String, nullable=False` | where to reach the server |
| `port` | `INT NOT NULL` | `Integer, nullable=False` | |
| `key` | `TEXT NOT NULL` | `String, nullable=False` | the game server's Fernet key, **stored encrypted with the SHARED_SECRET** |

A row here means "a game server told us it exists and here's how to reach it (and how to
verify tokens for it)." See [doc 07](07-servers-interface.md) and [doc 09](09-security.md) for
how `key` is produced and used.

### `userserver` — many-to-many: which user is at which server

| Column | SQL type | Notes |
|---|---|---|
| `username` | `TEXT REFERENCES "user"(username) ON DELETE CASCADE` | part of composite PK |
| `idserver` | `INT REFERENCES gameserver(id) ON DELETE CASCADE` | part of composite PK |

This is the **join table** linking players to game servers. Its main purposes:
- Count how many users are connected to each server (for load balancing).
- Tell whether a user is currently "playing" (`/users/playing`).

In the ORM it's an association `Table` named `userservers`, wired with
`relationship(..., secondary=userservers, back_populates=...)` on both `User.servers` and
`GameServer.users`.

> ⚠️ Reality check: although the schema and queries exist for `userserver`, **nothing in the
> current code path actually inserts rows into it.** The dispatcher and game server don't
> write to it. So in practice `connected_users` will be 0 and "playing" will be false for
> everyone right now. This is one of the unfinished seams — see [doc 12](12-known-issues.md).

## Entity relationship diagram

```
   ┌──────────────┐         ┌────────────────┐         ┌──────────────┐
   │     user     │         │   userserver   │         │  gameserver  │
   ├──────────────┤         ├────────────────┤         ├──────────────┤
   │ username PK  │1───────∞│ username  FK PK│∞───────1│ id        PK │
   │ password     │         │ idserver  FK PK│         │ ip           │
   │ salt         │         └────────────────┘         │ port         │
   │ balance      │           (junction /              │ key (enc.)   │
   └──────────────┘            many-to-many)           └──────────────┘
```

## The ORM layer — `orm/orm.py`

```python
Base = declarative_base()

userservers = Table('userserver', Base.metadata,
    Column('username', String, ForeignKey('user.username', ondelete='CASCADE'), primary_key=True),
    Column('idserver', Integer, ForeignKey('gameserver.id', ondelete='CASCADE'), primary_key=True))

class User(Base):        # table 'user'
class GameServer(Base):  # table 'gameserver'
```

## The data-access layer — `model/database_actions.py`

This module holds **all** the functions that read/write the DB. Routes call these; nothing
else touches SQLAlchemy. Each function opens a `SessionLocal()` context, handles
`SQLAlchemyError`, and returns plain values (never leaks ORM sessions).

| Function | What it does | Returns |
|---|---|---|
| `add_user(username, password, salt, balance)` | Insert a new `User` | `True` on success, error string on failure |
| `get_user(username)` | Fetch one `User` by PK | `User` or `None` |
| `get_servers_with_user_count()` | Join `gameserver`↔`userserver`↔`user`, count connected users per server, attach a **hard-coded `max_users = 10`** | list of tuples `(id, ip, port, connected_users, max_users, key)` or `None` |
| `is_user_playing(username)` | Is there a `userserver` row for this user? | `bool` |
| `register_server(server)` | Insert a `GameServer`, refresh to get its new `id` | the new `id`, or `False` |
| `get_server_key(server_id)` | Fetch a game server's (encrypted) `key` | the key string or `None` |
| `update_users_balance(results)` | For each `Result`, add `balance_difference` to that user's balance | `True` / `False` / error string |

Two things to internalize:
- **`max_users` is not stored in the DB** — it's injected as the literal `10` in the query.
  So every server is treated as capacity 10 for load-balancing math.
- **Balance updates are additive** (`user.balance += result.balance_difference`), so a
  `Result` of `-100` subtracts 100.

The connection itself is configured in `database/__init__.py`: it reads `DATABASE_URL` from
the environment (in Docker that's `postgresql://postgres:postgres@postgres:5432/blackjack`),
falling back to a local `BlackJack` DB if unset.

Next: [05 — database_interface](05-database-interface.md).
