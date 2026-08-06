# BlackJack

A multiplayer, online Blackjack game built as a small **distributed system**
(university course project).

Players register and log in on a **central server**, which dispatches them to one of
potentially many **game servers** running the actual card game in real time over
Socket.IO. The system tolerates **network partitions**: a game server keeps playing on
its own while central is unreachable and reconciles balances when the link heals.

```
Browser ── HTTP ──▶ CENTRAL SERVER (accounts, dispatch, balances) ──▶ PostgreSQL
   │                       ▲ register / heartbeat / results (JWT)
   └─ POST /join + token ─▶ GAME SERVER(s) (Socket.IO gameplay, durable outbox)
```

## Quick start

```bash
python secret_generator.py   # writes SHARED_SECRET to .env (once)
docker compose up --build
```

Then open http://localhost:16000, register, log in and hit **Play**.

## Documentation

Full documentation lives in [`docs/`](docs/README.md): architecture, the
distributed-systems mechanisms (heartbeats, durable outbox, idempotent
reconciliation), security model, flows, and the scripted
**partition-tolerance demo**.

## Tests

```bash
poetry install
poetry run pytest
```
