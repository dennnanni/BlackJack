# 04 — Data Model

## Central: PostgreSQL, three tables

Defined once, in the SQLAlchemy models in `central_server/db.py`. `init_db()` runs
`create_all` at startup, so there is no SQL script to run by hand and no second
copy of the schema to keep in sync.

### `user` — player accounts

| Column | Type | Notes |
|---|---|---|
| `username` | `TEXT PRIMARY KEY` | the login id; no separate numeric id |
| `password` | `TEXT NOT NULL` | PBKDF2-HMAC-SHA256 hash, base64 (never plaintext) |
| `salt` | `TEXT NOT NULL` | per-user base64 salt |
| `balance` | `NUMERIC(10,2)` | the **balance of record**; new users start at 1000 |

### `gameserver` — the live registry

| Column | Type | Notes |
|---|---|---|
| `id` | `SERIAL PRIMARY KEY` | assigned at registration, echoed back to the server |
| `host`, `port` | `TEXT`, `INT` | the address the *browser* will be sent to |
| `capacity` | `INT` | reported by the server at registration (default 10) |
| `load` | `INT` | current player count, **reported by heartbeats** |
| `last_seen` | `DOUBLE PRECISION` | unix timestamp of the last heartbeat |

`load` and `last_seen` replace the old `userserver` join table and its
never-populated `connected_users` counting: liveness and load are **pushed by the
server that knows them**, not derived by central.

A server is *eligible for dispatch* iff `last_seen ≥ now − HEARTBEAT_TTL` **and**
`load < capacity`. Dead servers simply age out of that predicate; their rows stay
(harmlessly) in the table.

### `applied_round` — the idempotency ledger

| Column | Type | Notes |
|---|---|---|
| `round_id` | `TEXT PRIMARY KEY` | UUID4 minted by the game server at round end |
| `applied_at` | `DOUBLE PRECISION` | unix timestamp; entries older than 7 days are pruned |

A row here means "this round's deltas are already in the balances". The PK is what
makes duplicate deliveries collapse into one effect.

## Game server: the SQLite outbox

Each game server owns a private SQLite file (`OUTBOX_PATH`), not shared with anyone:

```
pending(round_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at REAL NOT NULL)
```

`payload` is the JSON list of `{username, balance_difference}` records. Entries are
inserted at round end (before the room is even notified) and deleted only when
central ACKs that `round_id`. In Docker each game server mounts a named volume for
it, so results survive container restarts mid-partition.

## The wire contract (`shared/messages.py`)

The only code shared between the two roles: the JSON field-name constants and

```python
@dataclass
class Result:
    username: str
    balance_difference: float
```

produced by `Game.determine_result()` on the game server and parsed back by
`central_server/api.py` on delivery. Deltas are **additive**, which is what makes
"apply once, in any order, whenever the link heals" a safe reconciliation model.

Next: [05 — Security](05-security.md).
