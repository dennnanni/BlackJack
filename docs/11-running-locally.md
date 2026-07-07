# 11 — Running & Developing Locally

Two ways to run: **Docker Compose** (closest to "the whole system at once") or **bare Poetry**
(handy for iterating on one service). Both need a `SHARED_SECRET`.

## Step 0 — Generate the shared secret

Every security-sensitive service refuses to start without `SHARED_SECRET`. Generate it into a
`.env` at the repo root:

```bash
python secret_generator.py        # writes  SHARED_SECRET=<fernet key>  to ./.env
```

`.env` is git-ignored. Keep the **same** `.env` for all services in a given run — they must
share the secret.

---

## Option A — Docker Compose (recommended for a full run)

`startup.sh` builds the Poetry base image then brings everything up:

```bash
./startup.sh
# equivalently:
#   docker build -t ppython -f Dockerfile-poetry .     # only needed once
#   docker compose up --build
```

`docker-compose.yml` starts five things:

| Service | Image/cmd | Ports (host→container) | Notes |
|---|---|---|---|
| `postgres` | `postgres:17` | (internal) | db `blackjack`, user/pass `postgres/postgres`, persisted in a named volume |
| `database_interface` | `poetry run database` | (internal :5001) | `DATABASE_URL=postgresql://postgres:postgres@postgres:5432/blackjack` |
| `servers_interface` | `poetry run servers` | `16001 → 5002` | `DATABASE_URL=http://database_interface:5001` |
| `client_interface` | `poetry run client` | `16000 → 5000` | `DATABASE_URL=http://database_interface:5001` |
| `game_server_1` | `poetry run game_server` | `8000 → 8000` | `CENTRAL_SERVER_URL=http://servers_interface:5002` |

Then open **http://localhost:16000** for the player web app.

Things to know:
- The repo is bind-mounted into `/var/www` for the three central services (live code), but the
  `WORKDIR` in the image is `/app` (where `poetry install` ran). The game server is **not**
  bind-mounted.
- `game_server_1`'s `.env`/`SHARED_SECRET`: make sure your `.env` is available to the build/run
  so the game server (and the central services) get the same secret. The compose file sets
  `SERVER_HOST=127.0.0.1` for the game server — note that this is the address it *advertises to
  central*, so adjust it if you want other containers/browsers to reach it by that address.
- To run **more game servers**, copy the `game_server_1` block to `game_server_2`, give it a
  different host port, and the dispatcher will start balancing across them (once the
  `userserver` population gap is addressed — see [doc 12](12-known-issues.md)).

Tear down with `docker compose down` (add `-v` to wipe the Postgres volume).

---

## Option B — Bare Poetry (one or more services by hand)

Install deps once:

```bash
poetry install
```

You'll need a Postgres reachable at the `DATABASE_URL` the DB service expects. Either run the
compose `postgres` service alone (`docker compose up postgres`) or point `DATABASE_URL` at a
local Postgres with a `BlackJack` database (that's the fallback the code uses when
`DATABASE_URL` is unset — see `database/__init__.py`).

Then start each service in its own terminal (each reads `.env` for `SHARED_SECRET`):

```bash
poetry run database       # :5001  (start this first; others call it)
poetry run servers        # :5002
poetry run client         # :5000
poetry run game_server    # :8000  (needs servers_interface up to register)
```

Useful env overrides when running bare:
```bash
# client_interface / servers_interface need to find the DB service:
DATABASE_URL=http://localhost:5001 poetry run client
# game server needs to find central + advertise itself:
CENTRAL_SERVER_URL=http://localhost:5002 SERVER_PORT=8000 SERVER_HOST=127.0.0.1 poetry run game_server
```

---

## Running the tests

```bash
poetry run pytest game_server          # the solid game-logic suite (recommended)
poetry run pytest main_server/common   # shared-structures test
```

Caveats:
- `main_server/database_interface/test/test_database_actions.py` is **stale** (asserts an old
  return value) and will fail. (doc 12)
- `main_server/servers_interface/test/test_http.py` is an **integration** harness: it needs a
  running `servers_interface`, plus `SHARED_SECRET` and `TEST_KEY` env vars
  (`TEST_KEY` can be generated with `poetry run python main_server/servers_interface/test/key_gen.py`).

`.vscode/settings.json` configures the VS Code Test Explorer to use pytest against
`game_server`, so the game tests "just work" in the IDE.

---

## The database schema

The ORM auto-creates tables on `database_interface` startup
(`Base.metadata.create_all`), so you normally don't run SQL by hand. If you want to inspect or
bootstrap manually, `database/db_create.sql` is the reference schema (see [doc 04](04-data-model.md)).

Next: [12 — Known Issues & Rough Edges](12-known-issues.md).
