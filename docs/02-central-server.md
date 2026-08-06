# 02 — Central Server

One Flask application (`central_server/`), one process, two faces:

- **`web.py`** — the player-facing web app (untrusted browsers).
- **`api.py`** — the game-server-facing API (semi-trusted peers holding the shared secret).

Both call **`db.py`** directly; there is no HTTP inside the central tier.

## db.py — the database layer

Owns the SQLAlchemy engine (from `DATABASE_URL`) and the four models `User`,
`GameServer`, `Seat`, `AppliedRound` (see [04 — Data Model](04-data-model.md)).
`init_db()` runs `create_all` at startup, so missing tables are created
automatically.

All access goes through small functions that open a session, catch
`SQLAlchemyError`, and return plain values:

| Function | Purpose |
|---|---|
| `add_user`, `get_user` | account storage |
| `register_server(host, port, capacity)` | insert a game server, return its id |
| `heartbeat(server_id, players)` | stamp `last_seen = now`, store `load = len(players)`, renew those players' seats |
| `get_live_servers(ttl)` | servers seen within `ttl` **and** with `load < capacity` |
| `take_seat(username, server_id, ttl)` | claim the player's single seat; `False` if they hold one on a live server |
| `apply_results(round_id, results)` | idempotent balance update (see below) |
| `prune_applied_rounds(max_age)` | ledger housekeeping |

Balance updates are **additive**, which is what makes out-of-order and repeated
(deduplicated) delivery safe. They are also issued as a single SQL statement
(`UPDATE user SET balance = balance + :delta`) rather than read-modify-written in
Python: two rounds of the same player arriving concurrently — quite possible, since
several game servers drain their outboxes independently — would otherwise overwrite
each other's update and silently lose one delta.

## web.py — player routes

| Route | What it does |
|---|---|
| `GET /`, `GET /login` | login/registration page (redirects home if already logged in) |
| `POST /register` | PBKDF2-hash the password, create the user with balance 1000 |
| `POST /login` | fetch user, hash the attempt with the stored salt, compare |
| `GET /user/<username>` | home page; the balance is rendered **server-side** (no sockets) |
| `POST /play` | dispatch (below) |
| `POST /logout` | clear the session |

Login state is a Flask-Login session (`UserSession`, keyed by username). Unknown
usernames and wrong passwords both re-render the page with an error (no 500s, no
user-enumeration difference).

**Dispatch (`POST /play`):**
1. reject if the balance is ≤ 0;
2. pick the **least-loaded** of `db.get_live_servers(HEARTBEAT_TTL)` — the servers
   whose last heartbeat is fresh and that have free seats; if none, the home page
   shows "no game server available";
3. `db.take_seat(username, server.id, HEARTBEAT_TTL)` — claim the player's **one**
   seat before minting a token for it. Refused if they are already seated on a live
   server, which is what stops one account from playing two tables against the same
   balance (see [06 §6.6](06-distributed-systems.md#66-one-account-one-table-the-seat-lease));
4. `auth.mint_join_token(username, balance, server_id)` — a 2-minute JWT;
5. render `dispatch.html`, a tiny page with a hidden form that auto-submits the token
   to `http://<server.host>:<server.port>/join`.

## api.py — game-server routes

All under `/api/servers/`, all authorized by a Bearer JWT signed with the
`SHARED_SECRET` (see [05 — Security](05-security.md)).

| Route | Body | Behavior |
|---|---|---|
| `POST /register` | `{host, port, capacity}` | Bootstrap: any bearer signed with the secret is accepted (no `server_id` claim yet). Inserts the row, returns `{server_id}`, 201. |
| `POST /heartbeat` | `{players: [username]}` | Requires the `server_id` claim. Updates `last_seen`, sets `load = len(players)`, and renews the seat leases of exactly those players. Returns 404 for unknown ids, which tells the game server to re-register (e.g. after a DB reset). |
| `POST /results` | `{round_id, results: [{username, balance_difference}]}` | Requires the `server_id` claim. **Idempotent** — see below. Returns `{success: true}`. |

**Idempotent result application** (`db.apply_results`): if `round_id` is already in
the `applied_round` ledger, return success *without touching balances* (the game
server just needed its ACK). Otherwise apply every delta and insert the ledger row
**in the same transaction** — a concurrent duplicate dies on the primary-key conflict
instead of double-applying, and the retry then hits the already-applied path.

## reaper.py — periodic housekeeping

A daemon thread started by `create_app()`. Every `REAPER_INTERVAL` (5 s) it:

- prunes `applied_round` entries older than 7 days.

Note the design choice: **failure detection needs no thread at all.** Dispatch
filters on `last_seen` at pick time, so a server that stops heartbeating drops out
by itself and reappears the moment it resumes. That leaves the reaper with nothing
but housekeeping.

## Configuration (`config.py`)

| Variable | Default | Meaning |
|---|---|---|
| `SHARED_SECRET` | *(required, from `.env`)* | HS256 key for every JWT in the system |
| `DATABASE_URL` | local postgres | SQLAlchemy URL |
| `CENTRAL_PORT` | 5000 | listen port |
| `SECRET_KEY` | random per boot | Flask session-cookie key |
| `HEARTBEAT_TTL` | 15 s | freshness window for dispatch (3× the heartbeat interval) |
| `REAPER_INTERVAL` | 5 s | reaper period |
| `JOIN_TOKEN_TTL` | 120 s | join-token lifetime |
| `SEAT_GRACE` | 30 s | how long a freshly claimed seat is protected from release, i.e. how long the dispatched player has to actually land on the server |

Next: [03 — Game Server](03-game-server.md).
