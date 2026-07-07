# 02 — Central Server

One Flask application (`central_server/`), one process, two faces:

- **`web.py`** — the player-facing web app (untrusted browsers).
- **`api.py`** — the game-server-facing API (semi-trusted peers holding the shared secret).

Both call **`db.py`** directly; there is no HTTP inside the central tier.

## db.py — the database layer

Owns the SQLAlchemy engine (from `DATABASE_URL`) and the three models `User`,
`GameServer`, `AppliedRound` (see [04 — Data Model](04-data-model.md)).
`init_db()` runs `create_all` at startup, so missing tables are created
automatically.

All access goes through small functions that open a session, catch
`SQLAlchemyError`, and return plain values:

| Function | Purpose |
|---|---|
| `add_user`, `get_user` | account storage |
| `register_server(host, port, capacity)` | insert a game server, return its id |
| `heartbeat(server_id, load)` | stamp `last_seen = now`, store the reported load |
| `get_live_servers(ttl)` | servers seen within `ttl` **and** with `load < capacity` |
| `apply_results(round_id, results)` | idempotent balance update (see below) |
| `prune_applied_rounds(max_age)` | ledger housekeeping |

Balance updates are **additive** (`user.balance += delta`), which is what makes
out-of-order and repeated (deduplicated) delivery safe.

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
2. `dispatcher.pick_server()` — the **least-loaded** server among those whose last
   heartbeat is fresher than `HEARTBEAT_TTL` and that have free seats; if none, the
   home page shows "no game server available";
3. `auth.mint_join_token(username, balance, server_id)` — a 2-minute JWT;
4. render `dispatch.html`, a tiny page with a hidden form that auto-submits the token
   to `http://<server.host>:<server.port>/join`.

## api.py — game-server routes

All under `/api/servers/`, all authorized by a Bearer JWT signed with the
`SHARED_SECRET` (see [05 — Security](05-security.md)).

| Route | Body | Behavior |
|---|---|---|
| `POST /register` | `{host, port, capacity}` | Bootstrap: any bearer signed with the secret is accepted (no `server_id` claim yet). Inserts the row, returns `{server_id}`, 201. |
| `POST /heartbeat` | `{load}` | Requires the `server_id` claim. Updates `load` + `last_seen`. Returns 404 for unknown ids, which tells the game server to re-register (e.g. after a DB reset). |
| `POST /results` | `{round_id, results: [{username, balance_difference}]}` | Requires the `server_id` claim. **Idempotent** — see below. Returns `{success: true}`. |

**Idempotent result application** (`db.apply_results`): if `round_id` is already in
the `applied_round` ledger, return success *without touching balances* (the game
server just needed its ACK). Otherwise apply every delta and insert the ledger row
**in the same transaction** — a concurrent duplicate dies on the primary-key conflict
instead of double-applying, and the retry then hits the already-applied path.

## reaper.py — failure detection, made visible

A daemon thread started by `create_app()`. Every `REAPER_INTERVAL` (5 s) it:

- logs game servers whose `last_seen` just crossed `HEARTBEAT_TTL` ("considered
  offline") and ones that came back;
- prunes `applied_round` entries older than 7 days.

Note the design choice: **dispatch exclusion never depends on the reaper.** The
dispatcher filters on `last_seen` itself, so failure detection works even if the
reaper thread lags; the reaper is the observable/log side of it plus housekeeping.

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

Next: [03 — Game Server](03-game-server.md).
