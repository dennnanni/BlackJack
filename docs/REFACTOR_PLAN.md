# BlackJack — Refactor & Simplification Plan

> **Status:** proposal / roadmap. Written against the current `develop` branch and the
> deep-dive docs in this folder ([01](01-architecture.md)–[13](13-getting-started.md)).
> **Goal:** strongly simplify the system while keeping the game-server / central-server
> distinction, keeping genuine distributed-systems concepts, and adding **network-partition
> tolerance** (a course requirement).

---

## 0. Decisions driving this plan

These were chosen up front because they shape everything below:

| # | Decision | Choice | Consequence |
|---|----------|--------|-------------|
| D1 | Central server shape | **One single Flask app** | The 3 services (`database_interface`, `client_interface`, `servers_interface`) collapse into one process; the DB becomes a local module accessed directly via SQLAlchemy. No more HTTP-around-the-DB. |
| D2 | Database engine | **Keep PostgreSQL** | Stays a Docker container. ORM models barely change. |
| D3 | Auth / crypto | **Single shared secret** | One `SHARED_SECRET` for all server↔central auth *and* for signing the player join-JWT. Drops the Fernet handshake, per-server keys, and encrypted-key storage. Keeps PBKDF2 password hashing. |
| D4 | Partition durability | **On-disk outbox** | A game server persists unsent round results to a local store and retries until central acknowledges; central applies them idempotently. Survives restarts. |

---

## 1. Why we are doing this

The current system is a **four-process microservice mesh** (`database_interface`,
`client_interface`, `servers_interface`, `game_server`) plus a shared `common` package, three
separate cryptographic schemes, and Socket.IO used in places that don't need it. For a
university project this is **accidental complexity**: most of the moving parts exist to wire
services together, not to deliver the actual feature (a Blackjack game with a distributed
back-end).

What is genuinely valuable and worth keeping:
- The **central ↔ game-server split** (real horizontal-scaling story).
- The **well-tested game model** (`game_server/src/model/game_structures.py` + `tests/`).
- The **JWT join-token** idea (clean cross-trust-boundary auth).
- The **registration-with-retry** instinct (the seed of partition tolerance).

What is accidental complexity we will remove:
- The **DB-as-an-HTTP-service** indirection (`database_interface`).
- The **three-way crypto dance** (Fernet shared-secret handshake + per-server keys + JWT).
- **Socket.IO in the central server** (the player web app doesn't need real-time).
- The **`userserver` join table** and its broken `connected_users` counting.
- The **`common` package shared across process boundaries** and the duplicated `Result` class.

The headline trade: we go from **4 runnable services → 2** (central + game server), from
**3 crypto mechanisms → 2** (password hashing + one shared secret), and we replace fragile
counting with **heartbeat-reported load**. On that simpler base we add a clear, defensible
**partition-tolerance** layer.

---

## 2. Target architecture

### Before (today)

```
Browser ── HTTP/Socket ─▶ client_interface ─HTTP▶ database_interface ─ORM▶ Postgres
                                                          ▲
        ┌──────── HTTP/Socket ───────────┐                │ HTTP
        ▼                                │                │
   game_server ──── HTTP (encrypted) ─▶ servers_interface ┘
   (registers, reports results)        (register / results)
```
4 processes + Postgres, 3 crypto schemes, Socket.IO in 3 places.

### After (this plan)

```
                         ┌──────────────────────────────────────────┐
 Browser ── HTTP ───────▶│            CENTRAL SERVER (1 app)        │──ORM──▶ Postgres
   login/home/play       │  web/  (login, home, play)               │
                         │  api/  (register, heartbeat, results)    │
                         │  dispatcher + reaper (background)        │
                         └───────────────▲───────────▲──────────────┘
                                         │           │
            POST /join (+ join-JWT)      │ HTTP      │ HTTP (Bearer server-JWT)
  Browser ──────────────┐                │           │  register / heartbeat / results
                        ▼                │           │
                   game_server ──────────┘           │ 
                   (Socket.IO gameplay) ── on-disk outbox ── retries results until ACK
```
2 processes + Postgres, 1 shared secret (+ password hashing), Socket.IO **only** in the game
server. The central server is the source of truth; game servers operate autonomously during
partitions and reconcile via the outbox.

### CAP positioning (say this to the professor)

- **Accounts, dispatch, balances of record** live on the **central server** → effectively the
  **CP / source-of-truth** side. If central is unreachable, you cannot log in, cannot get
  dispatched to a new table, and balances of record cannot change.
- **In-progress gameplay** on a game server is **AP**: a round that has already started keeps
  running during a partition; results are buffered locally and delivered later.
- Convergence is achieved through **eventual consistency**: results are **additive deltas**
  carried with an **idempotency key (`round_id`)**, delivered **at-least-once** and applied
  **exactly-once** at central, so the final balance is correct regardless of retries, ordering,
  or duplicates.

---

## 3. Target repository structure

```
blackjack/
├── docker-compose.yml          # postgres + central + N game servers
├── Dockerfile                  # one image, used by both roles
├── pyproject.toml              # TWO entry points: central, game_server
├── secret_generator.py         # unchanged: writes SHARED_SECRET to .env
├── shared/                     # tiny: the wire contract only
│   ├── __init__.py
│   └── messages.py             # Result dataclass + field-name constants (single source of truth)
│
├── central_server/
│   ├── __init__.py             # create_app(): blueprints + start reaper thread
│   ├── main.py                 # entry point (poetry run central)
│   ├── config.py               # SHARED_SECRET, DATABASE_URL, HEARTBEAT_TTL, etc.
│   ├── db.py                   # engine, SessionLocal, ORM models, create_all
│   ├── auth.py                 # PBKDF2 hashing + JWT mint/verify (join + server tokens)
│   ├── dispatcher.py           # pick least-loaded LIVE server
│   ├── reaper.py               # background: mark stale servers offline
│   ├── web.py                  # Blueprint: /, /login, /register, /logout, /user/<u>, /play
│   ├── api.py                  # Blueprint: /api/servers/register|heartbeat|results
│   └── templates/
│       ├── access.html         # (moved from client_interface)
│       └── home.html           # (moved; balance rendered server-side, no Socket.IO)
│
└── game_server/
    ├── __init__.py             # create_app(): register-with-retry, start heartbeat+sender threads
    ├── main.py                 # entry point (poetry run game_server)
    ├── config.py               # SERVER_HOST/PORT, CENTRAL_URL, SHARED_SECRET, OUTBOX_PATH
    ├── central_client.py       # register / heartbeat / send_results (HTTP + Bearer server-JWT)
    ├── outbox.py               # on-disk durable result queue + idempotency keys
    ├── join.py                 # GET / (game UI), POST /join (verify join-JWT)
    ├── events.py               # Socket.IO: join / bet / player_action
    ├── loop.py                 # round state machine (was game_loop.py)
    ├── game/
    │   └── model.py            # Card, Deck, Hand, User, Game, Table, TableManager (was game_structures.py)
    └── templates/
        └── index.html          # the re-enabled game UI
```

`pyproject.toml` shrinks to two scripts:

```toml
[tool.poetry.scripts]
central     = "central_server.main:main"
game_server = "game_server.main:main"
```

---

## 4. Data model after refactor

Three tables → still three, but simpler and correct:

```
user(username PK, password, salt, balance)            -- unchanged
gameserver(id PK, host, port, capacity,
           load, last_seen)                            -- key column REMOVED; load+last_seen ADDED
applied_round(round_id PK, applied_at)                 -- NEW: idempotency ledger
-- userserver table: DELETED
```

Changes vs. today (see [doc 04](04-data-model.md)):
- **`gameserver.key` removed** — no per-server keys anymore (D3).
- **`gameserver.load` + `gameserver.last_seen` added** — load is *reported* by heartbeats, not
  computed by a join. `capacity` replaces the hard-coded `max_users = 10`.
- **`userserver` deleted** — its only jobs (counting connected users, "is playing") are
  replaced by heartbeat-reported load. This kills a whole class of bugs (it was never
  populated; see [doc 12](12-known-issues.md) #3).
- **`applied_round` added** — the idempotency ledger that makes result retries safe.

`central_server/db.py` keeps the SQLAlchemy `User`/`GameServer` models almost verbatim, adds
`AppliedRound`, and calls `Base.metadata.create_all(engine)` at startup (as today). Balance
updates stay **additive** (`user.balance += delta`).

---

## 5. Auth & crypto after refactor (D3)

We keep exactly **two** mechanisms.

### 5.1 Password hashing — KEEP unchanged
PBKDF2-HMAC-SHA256 + per-user salt, exactly as in
`client_interface/.../utils/security.py` (see [doc 09](09-security.md) §2). Moves into
`central_server/auth.py`. Because the DB is now local, login no longer needs the
salt→hash→compare round-trip over HTTP — `auth.py` reads the user row directly and compares.

### 5.2 One shared secret for everything else
`SHARED_SECRET` (still generated by `secret_generator.py`) is used as the **HS256 signing key**
for two kinds of JWT:

**(a) Server token** — proves a game server is part of the system.
```python
# game_server/central_client.py — attached to every call to central
bearer = jwt.encode({"server_id": MY_ID, "iat": now, "exp": now + 60},
                    SHARED_SECRET, algorithm="HS256")
headers = {"Authorization": f"Bearer {bearer}"}
# (registration is the bootstrap: no server_id yet, so the claim is omitted and
#  central assigns one — knowledge of SHARED_SECRET is what authorizes the call.)
```

**(b) Join token** — central authorizes a player to enter a specific game server.
```python
# central_server/auth.py
def mint_join_token(username, balance, server_id):
    return jwt.encode({"sub": username, "balance": float(balance),
                       "server_id": server_id, "iat": now, "exp": now + 120},
                      SHARED_SECRET, algorithm="HS256")

# game_server/join.py
payload = jwt.decode(token, SHARED_SECRET, algorithms=["HS256"])
if payload["server_id"] != MY_ID:   # token was minted for a different server
    abort(403)
username, balance = payload["sub"], payload["balance"]
```

### What this deletes (the big win)
- The **Fernet registration handshake** (`game_server/src/central_api.py` double-encryption,
  `encryption.py`, `servers_interface` re-encrypting and returning the encrypted blob).
- **Per-server keys** and the `GET /servers/key` endpoint.
- **Storing keys encrypted in the DB**.

### Security note to put in the report (defensible trade-off)
With a single shared secret, *any* game server could technically verify a token minted for
another. We bind each join token to one server via the **`server_id` claim** + a **2-minute
expiry**, and the only holders of the secret are our own trusted processes. We also **close a
real existing hole**: today the browser sends its own `balance` in the Socket.IO `join` event
(the game server trusts client-supplied money). After the refactor the **balance comes from
the signed join token**, so the client can't forge it.

---

## 6. Distributed-systems features (the graded core)

Four cooperating mechanisms give partition tolerance + eventual consistency. None is heavy;
together they tell a complete story.

### 6.1 Service discovery via registration (KEEP + simplify)
On startup a game server `POST /api/servers/register {host, port, capacity}` (authorized by
knowing `SHARED_SECRET`). Central inserts a `gameserver` row and returns `server_id`. The
existing **retry loop** (5 attempts, 2 s apart, exit on failure — see [doc 08](08-game-server.md))
stays: it's the first piece of partition tolerance (central may be down at boot).

### 6.2 Failure detection via heartbeats (NEW, replaces userserver counting)
Every `HEARTBEAT_INTERVAL` (e.g. 5 s) the game server sends:
```
POST /api/servers/heartbeat        Authorization: Bearer <server-JWT>
{ "load": <current number of connected players> }
```
Central updates `gameserver.last_seen = now()` and `gameserver.load = load`.

A background **reaper** (`central_server/reaper.py`) runs every few seconds and marks any
server with `last_seen < now - HEARTBEAT_TTL` (e.g. TTL = 3× interval) as **stale**. The
**dispatcher only considers servers seen within the TTL** and with `load < capacity`, then
picks `min(load)`. When heartbeats resume, the server is automatically eligible again.

This single change: (a) removes the broken `userserver`/`connected_users` machinery,
(b) gives correct load-based balancing, and (c) is textbook **heartbeat failure detection**.

### 6.3 The result outbox: at-least-once delivery (NEW, D4)
When a round finishes, the game server creates a unique **`round_id` (UUID4)** and **writes the
results to a local on-disk outbox before doing anything else** (a tiny SQLite file at
`OUTBOX_PATH`, or a JSON-lines file):

```
outbox table:  pending(round_id PK, payload TEXT, created_at)
```

A background **sender thread** continuously tries to deliver each pending entry:
```
POST /api/servers/results   Authorization: Bearer <server-JWT>
{ "round_id": "<uuid>", "results": [{"username":..,"balance_difference":..}, ...] }
```
- On HTTP **200** → delete the entry from the outbox.
- On failure/timeout (partition!) → leave it, back off, retry later.

Because results are written to disk **before** delivery is attempted, a game-server crash or a
long central outage cannot lose them. This is the core of the partition story.

### 6.4 Idempotent application: exactly-once effect (NEW)
The central `/api/servers/results` handler is **idempotent**:
```python
if session.get(AppliedRound, round_id):     # already applied
    return {"success": True}, 200            # ACK again — safe for retries
for r in results:
    user = session.get(User, r["username"])
    if user: user.balance += r["balance_difference"]
session.add(AppliedRound(round_id=round_id, applied_at=now()))
session.commit()
return {"success": True}, 200
```
At-least-once delivery (6.3) + idempotent receiver (6.4) = **effectively-once**. Retries,
duplicates, and re-sends after a heal all converge to the correct balance because the deltas
are additive and the `round_id` deduplicates.

### 6.5 Autonomous gameplay during a partition
Game state (`TableManager`, `user_map`, the per-table `GameLoop`) is **in-memory in the game
server** (as today). During a central partition:
- **In-progress rounds keep running** — betting, hitting, dealer, results all work locally.
- **Finished rounds queue** in the outbox and flush when the link returns.
- **New players cannot join** (joining needs central to mint a token and dispatch) — this is
  acceptable and is the deliberate boundary between the AP and CP halves. Document it.

**Bounded-overdraft note:** during a long partition a player keeps playing against the balance
captured at join time, so balances of record lag reality and a player could in principle
overdraw. We accept this (it's the AP trade-off) and bound it: balances reconcile on heal via
additive deltas, and because a player can only be at one game server and can't join a new one
during a partition, there is **no concurrent double-spend** across servers.

### Distributed-systems concepts checklist (for the write-up)
- [x] Horizontal scaling / replicas (many game servers, one central)
- [x] Service discovery & registration (with retry)
- [x] Failure detection (heartbeats + reaper + TTL)
- [x] Load-aware dispatch (least-connections over *live* servers)
- [x] **Partition tolerance** (autonomous gameplay + durable outbox)
- [x] **Eventual consistency** (deltas reconcile after heal)
- [x] **Idempotency / exactly-once effect** (`round_id` ledger)
- [x] Authentication across a trust boundary (signed tokens)

---

## 7. Phased migration plan

Each phase ends with **runnable software** and a **verification step**. Do them in order; you
can stop after any phase and still have something that works. Work on a branch off `develop`
(e.g. `feature/simplify`).

> Reminder: keep an `.env` with `SHARED_SECRET` (`python secret_generator.py`) throughout.

### Phase 0 — Safety net (½ day)
- Branch from `develop`.
- Make the **game-model tests pass and pin them**: `poetry run pytest game_server`. These are
  your regression net for everything in `game/model.py`. Fix the trivial `Result.to_dict()`
  missing-`return` bug ([doc 12](12-known-issues.md) #5) now.
- Delete/disable the stale `test_database_actions.py` ([doc 12](12-known-issues.md) #8) so the
  suite is green.
- **Verify:** test suite green; app still boots via current `docker-compose`.

### Phase 1 — Collapse the central server into one app (2–3 days, biggest structural win)
Goal: one process owning the DB; **no inter-service HTTP**. Behavior stays equivalent.

Steps:
1. Create `central_server/` with `__init__.py`, `main.py`, `config.py`.
2. Move the ORM + DB session from `database_interface/.../{__init__,orm,model}` into
   `central_server/db.py`. Convert `database_actions.py` functions into direct calls (they
   already encapsulate sessions nicely).
3. Move the player web app (`client_interface/.../controller/web_controller.py`,
   `routes_controller.py`, `templates/`, `model/structures.py` `UserSession`, Flask-Login
   setup) into `central_server/web.py` + `templates/`. **Replace every `get_request`/
   `post_request` to `database_interface` with a direct function call** into `db.py`.
4. Move the game-server-facing endpoints (`servers_interface/.../servers_controller.py`) into
   `central_server/api.py`, again calling `db.py` directly instead of over HTTP.
5. Create `shared/messages.py` with the single `Result` dataclass + field constants; delete
   `common/http_requests.py` (central no longer makes internal HTTP) and fold the rest of
   `common` into `shared` or `central_server`.
6. Update `pyproject.toml`: replace the 3 central scripts with one `central` entry point.
7. Update `docker-compose.yml`: replace the 3 central services with one `central` service
   (still depends on `postgres`).

Delete after this phase: `main_server/` entirely (its contents now live in `central_server/`
and `shared/`).

**Verify:** register, log in, see balance, click Play, get redirected to a game server, and
results still update balances — all with the *old* crypto still in place. (Crypto gets
simplified in Phase 2; don't change two things at once.)

### Phase 2 — Single shared secret (1–2 days)
Goal: implement §5. Replace the Fernet handshake and per-server keys with shared-secret JWTs.

Steps:
1. `central_server/auth.py`: add `mint_join_token`, `verify_server_token`, keep PBKDF2.
2. `central_server/api.py`:
   - `/api/servers/register`: authorize by verifying a bootstrap server-JWT (or accept any
     caller that signs with the secret); store `host, port, capacity`; return `server_id`.
     Remove the Fernet decrypt/re-encrypt/echo logic.
   - `/api/servers/results`: authorize via `Authorization: Bearer` server-JWT; remove the
     `/servers/key` lookup + per-server-key decode.
3. `game_server/central_client.py`: rewrite `register_game_server` to a plain authorized POST;
   stop generating/sending a Fernet key. Attach a Bearer server-JWT to all calls.
4. `game_server/join.py`: verify the join token with `SHARED_SECRET` and check the `server_id`
   claim. Read `username` + `balance` **from the token** (stop trusting client-supplied balance).
5. Drop `gameserver.key` from the model; delete `encryption.py`, `key_gen.py`, the
   `/servers/key` endpoint.

**Verify:** full login→play→result flow works with only password-hashing + shared-secret JWT.

### Phase 3 — De-Socket.IO the central server (½–1 day)
Goal: the player web app uses plain HTTP; Socket.IO survives **only** in the game server.

Steps:
1. `home.html`: render balance **server-side** in `/user/<username>` (central reads the DB
   directly now), removing the `get_user_info` socket round-trip.
2. Replace the `get_game_server` socket event with a normal `POST /play` route that picks a
   server, mints the join token, and returns an auto-submitting form / redirect to the game
   server's `/join` (keep the existing hidden-form POST pattern from `home.html`).
3. Remove `SocketIO` from `central_server` entirely (and `manage_session=False`, the
   `event_handlers`, etc.).

**Verify:** login, home shows balance, Play dispatches correctly — with zero WebSockets on the
central server.

### Phase 4 — Heartbeats, load, reaper (1–2 days)
Goal: implement §6.2; delete `userserver`.

Steps:
1. DB: add `load`, `last_seen`, `capacity` to `gameserver`; drop `userserver`; drop
   `is_user_playing` / `get_servers_with_user_count` join logic.
2. `central_server/api.py`: add `/api/servers/heartbeat`.
3. `central_server/reaper.py`: background thread marking stale servers; start it in
   `create_app()`.
4. `central_server/dispatcher.py`: pick `min(load)` among servers with fresh `last_seen` and
   `load < capacity`.
5. `game_server/__init__.py`: start a heartbeat thread reporting `len(user_map)` (or live
   connection count) every interval.

**Verify:** start 2 game servers; confirm `load` updates and dispatch balances; kill one and
confirm the reaper drops it from dispatch within the TTL.

### Phase 5 — Partition tolerance: outbox + idempotency (2–3 days, the centerpiece)
Goal: implement §6.3–6.5.

Steps:
1. `shared/messages.py`: ensure `Result` round-trips cleanly; define the `/results` payload
   shape `{round_id, results[]}`.
2. `central_server/db.py`: add `AppliedRound`. `central_server/api.py`: make `/results`
   idempotent (§6.4).
3. `game_server/outbox.py`: on-disk store (SQLite at `OUTBOX_PATH`) with `enqueue(round_id,
   results)`, `pending()`, `ack(round_id)`.
4. `game_server/loop.py`: at round end, generate `round_id`, **enqueue to the outbox first**,
   then emit `round_results` to the room. Remove the direct `central_client.send_results` call
   from the hot path.
5. `game_server/central_client.py` + a **sender thread**: drain the outbox with retry/backoff;
   `ack` on HTTP 200.

**Verify (the demo, see §9):** start central + a game server, join a table, **sever the network
between them**, finish a round (results land in the outbox; gameplay continues), **restore the
network**, watch the sender flush and the balance reconcile. Send the same `round_id` twice and
confirm the balance only moves once.

### Phase 6 — Re-enable the game UI, polish, docs (1–2 days)
- Un-comment and reconcile `game_server/templates/index.html` with the **actual** event
  payloads (it currently references `res.outcome`/`res.payout`; the server emits `username` /
  `balance_difference` — see [doc 12](12-known-issues.md) #4). Wire it to open Socket.IO and
  emit `join` after `POST /join`.
- Add a Socket.IO `disconnect` handler in the game server to remove users from
  `user_map`/tables (today there is none — [doc 12](12-known-issues.md)).
- Harden the login lookup for unknown users ([doc 12](12-known-issues.md) #6); remove the
  plaintext-password `print`.
- Production-ish config knobs: move `SECRET_KEY` off the literal `'secret!'`.
- Rewrite tests (see §8). Update `docs/` to describe the new architecture.

---

## 8. Testing strategy

Keep the strong model tests; add a thin layer for the new distributed behavior.

- **Unit (keep):** `game_server` model tests move with the code to `game_server/game/model.py`
  imports; keep them green.
- **Idempotency (new, central):** call the `/results` handler twice with the same `round_id`
  and assert the balance changed once; assert two *different* round_ids both apply.
- **Outbox (new, game server):** enqueue → simulate a failing sender → assert entry persists
  and survives a reopen of the store → simulate success → assert `ack` removes it.
- **Failure detection (new, central):** insert a `gameserver` with an old `last_seen`; run the
  reaper; assert it's excluded from `dispatcher.pick()`.
- **Auth (new):** a join token with the wrong `server_id` or past `exp` is rejected by
  `game_server/join.py`.
- **Drop:** the stale `database_interface` test; the manual `servers_interface/test/test_http.py`
  becomes obsolete (replace with the idempotency test above).

---

## 9. Demonstrating partition tolerance (script for the professor)

With Docker (`central`, `postgres`, `game_server_1`):
1. Register + log in + Play → you're at a table on `game_server_1`.
2. **Partition:** `docker network disconnect <net> game_server_1` (or block the central port).
3. Play a full round. Observe: round completes locally; the central balance is **unchanged**;
   the result sits in the game server's outbox; the sender logs ret/ retries failing.
4. **Heal:** `docker network connect <net> game_server_1`.
5. Observe: the sender flushes; central applies the deltas; the player's balance of record
   **converges**. Re-trigger a resend (or duplicate the round_id) → balance does **not** double
   → idempotency proven.
6. Optional: kill `game_server_1` mid-partition and restart it → the on-disk outbox still holds
   the result → it's delivered after heal → **durability proven**.

This single demo exercises registration-retry, heartbeat failure detection, autonomous
gameplay, at-least-once delivery, durable buffering, and exactly-once application.

---

## 10. File-by-file migration map

| Today | Fate | Lands in |
|---|---|---|
| `main_server/database_interface/database/orm/orm.py` | move + edit (drop `key`/`userserver`, add load/last_seen/AppliedRound) | `central_server/db.py` |
| `.../database/model/database_actions.py` | move; called directly (no HTTP) | `central_server/db.py` |
| `.../database/controller/*_database_controller.py` | merge into central API/web | `central_server/api.py`, `web.py` |
| `main_server/client_interface/.../web_controller.py`, `routes_controller.py` | move; DB calls become direct | `central_server/web.py` |
| `.../client_interface/.../utils/security.py` | move; keep PBKDF2, simplify `create_token` | `central_server/auth.py` |
| `.../client_interface/.../dispatcher.py` | move; pick over *live* servers | `central_server/dispatcher.py` |
| `.../client_interface/.../templates/*.html` | move; balance server-rendered, no Socket.IO | `central_server/templates/` |
| `.../client_interface/.../model/structures.py` (`UserSession`) | move | `central_server/web.py` |
| `main_server/servers_interface/.../servers_controller.py` | move; drop Fernet/per-server-key | `central_server/api.py` |
| `main_server/common/structures.py` | split: wire types → shared; rest inlined | `shared/messages.py` |
| `main_server/common/response_fields.py` | move | `shared/messages.py` |
| `main_server/common/http_requests.py` | **delete** (no internal HTTP) | — |
| `game_server/src/central_api.py` | rewrite: plain authorized HTTP + outbox sender | `game_server/central_client.py` |
| `game_server/src/encryption.py` | **delete** (no Fernet) | — |
| `game_server/src/model/game_structures.py` | move (keep logic + tests) | `game_server/game/model.py` |
| `game_server/src/game_loop.py` | move; enqueue to outbox at round end | `game_server/loop.py` |
| `game_server/src/event_handlers.py` | move; read balance from token; report load | `game_server/events.py` |
| `game_server/src/controller/connection_controller.py` | move; verify shared-secret join-JWT | `game_server/join.py` |
| `game_server/tests/*` | keep; fix import paths | `game_server/tests/` |
| `main_server/servers_interface/test/*` | replace with idempotency/outbox tests | `game_server/tests/`, central tests |
| `database/db_create.sql` | update to new schema (or rely on `create_all`) | `database/db_create.sql` |
| `docker-compose.yml` | 3 central services → 1; keep postgres; N game servers | root |
| `pyproject.toml` | 4 scripts → 2 (`central`, `game_server`) | root |

---

## 11. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Phase 1 is a big move and could break the happy path silently | Keep crypto unchanged in Phase 1; verify the full flow before touching auth in Phase 2. Lean on the model tests. |
| In-memory game state lost on game-server restart | Out of scope to fully persist (acceptable for the course); the **outbox** ensures *finished* rounds aren't lost. Document the boundary. |
| Outbox + idempotency subtle bugs | Cover with the two targeted tests in §8; the demo in §9 is the acceptance test. |
| `applied_round` table grows forever | Prune rows older than e.g. 7 days in the reaper (cheap, optional). |
| Clock skew affecting JWT `exp` / heartbeat TTL | Use generous windows (120 s token, TTL = 3× interval); all processes share the host clock in the demo. |
| Single shared secret weaker than per-server keys | Documented trade-off (§5); bound by `server_id` claim + short expiry; closes the client-supplied-balance hole as a net security win. |

---

## 12. Definition of done

- Two runnable roles only: `poetry run central`, `poetry run game_server`.
- One central process owns Postgres directly; **no service-to-service HTTP inside the central
  tier**; **no Socket.IO in the central server**.
- Exactly two crypto mechanisms: PBKDF2 password hashing + one shared-secret JWT scheme.
- `gameserver` load comes from heartbeats; dead servers leave the dispatch set automatically;
  `userserver` is gone.
- A finished round is **never lost** across a central outage and **never double-applied**
  (durable outbox + `round_id` idempotency), demonstrable via §9.
- Game-model tests green; new idempotency/outbox/failure-detection/auth tests green.
- `docs/` updated to describe the new two-process architecture.

---

*This plan deliberately keeps the distributed-systems substance (the part the course is about)
and removes the plumbing that was only there to glue four services together. After it, the
"interesting" code is the game model and the partition-tolerance layer — exactly where the
attention should be.*
