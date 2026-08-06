# 08 — Running & Testing

## Prerequisite: the shared secret

```bash
python secret_generator.py     # writes SHARED_SECRET=... into .env
```

Both roles refuse to start without it. Do this once; Docker and local runs both read
the same `.env` (compose passes it via `env_file`).

## With Docker (recommended)

```bash
docker compose up --build
```

What comes up:

| Service | Image role | Host port |
|---|---|---|
| `postgres` | postgres:17, volume `postgres_data` | — |
| `central` | `poetry run central` | **16000** → 5000 |
| `game_server_1` | `poetry run game_server`, outbox volume `gs1_outbox` | **8001** |
| `game_server_2` | idem, volume `gs2_outbox` | **8002** |

Open **http://localhost:16000**, register, log in, hit **Play** — the browser is
forwarded to `localhost:8001` or `:8002` (game servers advertise
`SERVER_HOST=localhost` precisely so the *host* browser can reach them through the
published ports).

Compose defines two networks: `internal` (game servers ↔ central ↔ postgres) and
`frontend` (browser-facing side of the game servers). This exists so the
[partition demo](09-partition-demo.md) can sever only the server↔central link while
players keep playing.

> Schema changes: the ORM only creates *missing* tables. After pulling a change that
> alters columns, reset the volume: `docker compose down -v && docker compose up --build`.

## Locally with Poetry

```bash
poetry install
# terminal 1 — central (needs a reachable Postgres, or any SQLAlchemy URL):
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/blackjack poetry run central
# terminal 2 — a game server:
SERVER_PORT=8001 CENTRAL_URL=http://localhost:5000 OUTBOX_PATH=/tmp/gs1-outbox.db poetry run game_server
```

Any SQLAlchemy URL works for experiments (e.g. `DATABASE_URL=sqlite:///dev.db`).
Add more game servers by picking a different `SERVER_PORT`/`OUTBOX_PATH` per process.

## The test suite

```bash
poetry run pytest      # 41 tests
```

| Where | What it pins |
|---|---|
| `game_server/tests/test_{card_and_deck,hand,user,game,game_logic,tablemanager}.py` | the game model: hand values (multi-ace), blackjack detection, betting limits, payout rules (win/lose/push/dealer-bust), seating |
| `game_server/tests/test_outbox.py` | durability: entries survive reopen, only `ack` removes them, duplicate enqueue is a no-op |
| `game_server/tests/test_join_token.py` | join tokens: valid accepted; wrong-server, expired and forged rejected |
| `central_server/tests/test_dispatcher.py` | failure detection & dispatch: stale and full servers excluded, least-loaded wins, a recovered server becomes eligible again |
| `central_server/tests/test_results_idempotency.py` | exactly-once effect: same `round_id` applies once (unit + HTTP), different rounds both apply, unauthorized results rejected |

The central tests run against an in-memory SQLite database (see
`central_server/tests/conftest.py`) — no Postgres needed for testing.

## Environment variables (complete list)

| Variable | Used by | Default |
|---|---|---|
| `SHARED_SECRET` | both | *(required)* |
| `DATABASE_URL` | central | `postgresql://postgres:postgres@localhost:5432/blackjack` |
| `CENTRAL_PORT` | central | 5000 |
| `HEARTBEAT_TTL` / `REAPER_INTERVAL` | central | 15 / 5 |
| `SERVER_HOST` / `SERVER_PORT` | game server | 127.0.0.1 / 8000 |
| `CENTRAL_URL` | game server | http://localhost:5000 |
| `CAPACITY` / `HEARTBEAT_INTERVAL` | game server | 10 / 5 |
| `OUTBOX_PATH` | game server | `outbox.db` |
| `SECRET_KEY` | both | random per boot |

Next: [09 — Partition-Tolerance Demo](09-partition-demo.md).
