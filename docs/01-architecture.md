# 01 — Architecture

## The mental model

Two runnable roles plus a database:

```
                         ┌──────────────────────────────────────────┐
 Browser ── HTTP ───────▶│            CENTRAL SERVER (1 app)        │──ORM──▶ Postgres
   login/home/play       │  web.py   (login, home, play)            │
                         │  api.py   (register, heartbeat, results) │
                         │  reaper   (background ledger pruning)     │
                         └───────────────▲───────────▲──────────────┘
                                         │           │
            POST /join (+ join-JWT)      │ HTTP      │ HTTP (Bearer server-JWT)
  Browser ──────────────┐                │           │  register / heartbeat / results
                        ▼                │           │
                   GAME SERVER ──────────┘           │
                   (Socket.IO gameplay) ── on-disk outbox ── retries results until ACK
                   (1..N replicas)
```

| Role | Package | Entry point | Default port |
|---|---|---|---|
| **Central server** | `central_server/` | `poetry run central` | 5000 (Docker: 16000) |
| **Game server** | `game_server/` | `poetry run game_server` | 8000 (Docker: 8001, 8002) |

They share exactly one module: **`shared/messages.py`** — the wire contract (JSON
field names + the `Result` dataclass). Nothing else crosses the boundary as code.

## Why it is split this way

- **The central server is the source of truth.** It owns PostgreSQL directly (plain
  SQLAlchemy, no service in between), holds the accounts and the balances of record,
  and decides which game server a player goes to.
- **Game servers are the replicated, stateful workers.** Game logic is the
  CPU/connection-heavy part, so it is the piece designed to scale horizontally. Each
  game server keeps its tables **in memory** and can run rounds **autonomously**, even
  while central is unreachable.
- **The browser talks to both, with different protocols.** Plain HTTP (forms and
  redirects) to central — no WebSockets there — and Socket.IO only to the game server,
  where real-time actually matters.

## How the pieces communicate

| From → To | Transport | Purpose |
|---|---|---|
| Browser → central | HTTP (forms) | register, login, home page, Play |
| Browser → game server | HTTP `POST /join` (+ join-JWT), then Socket.IO | enter the table, then play in real time |
| Game server → central | HTTP + Bearer server-JWT | self-registration, heartbeats, round results |
| Central → PostgreSQL | SQLAlchemy / psycopg2 | persistence |

Note the direction: **central never calls a game server.** Everything between the two
servers is initiated by the game server, which is what makes the retry/outbox story
simple (there is exactly one talker and one listener per link).

## CAP positioning

- **Accounts, dispatch and balances of record** live on the central server — this is
  the **CP / source-of-truth** side. If central is down you cannot log in, cannot be
  dispatched to a new table, and the balance of record cannot change.
- **In-progress gameplay** on a game server is **AP**: a round that has started keeps
  running during a partition; finished rounds are buffered locally (on disk) and
  delivered later.
- **Convergence** is eventual consistency done safely: results are **additive deltas**
  keyed by a unique **`round_id`**, delivered **at-least-once** and applied
  **exactly once** at central (an idempotency ledger deduplicates), so the final
  balance is correct regardless of retries, ordering or duplicates.

The deliberate boundary: **during a partition, new players cannot join** (joining
needs central to mint a token), but everyone already seated keeps playing. See
[06 — Distributed-Systems Mechanisms](06-distributed-systems.md).

## Repository layout

```
BlackJack/
├── docker-compose.yml        # postgres + central + 2 game servers
├── Dockerfile                # one image, used by both roles
├── pyproject.toml            # Poetry config; the 2 entry points
├── secret_generator.py       # writes SHARED_SECRET to .env
├── shared/
│   └── messages.py           # wire contract: field names + Result
├── central_server/
│   ├── app.py                # create_app(): blueprints + reaper thread
│   ├── main.py               # entry point
│   ├── config.py             # SHARED_SECRET, DATABASE_URL, TTLs...
│   ├── db.py                 # engine, ORM models, data-access functions
│   ├── auth.py               # PBKDF2 hashing + JWT mint/verify
│   ├── reaper.py             # periodic ledger pruning
│   ├── web.py                # player-facing routes
│   ├── api.py                # game-server-facing routes
│   ├── templates/            # access.html, home.html, dispatch.html
│   └── tests/
└── game_server/
    ├── app.py                # create_app(): registration retry + threads
    ├── main.py               # entry point
    ├── config.py             # SERVER_HOST/PORT, CENTRAL_URL, OUTBOX_PATH...
    ├── central_client.py     # register / heartbeat / send_results
    ├── outbox.py             # durable result queue (SQLite)
    ├── join.py               # GET / + POST /join (join-token check)
    ├── events.py             # Socket.IO: join / bet / player_action / disconnect
    ├── loop.py               # the round state machine (one thread per table)
    ├── game/model.py         # Card, Deck, Hand, User, Game, Table, TableManager
    ├── templates/index.html  # the game UI
    └── tests/
```

Next: [02 — Central Server](02-central-server.md).
