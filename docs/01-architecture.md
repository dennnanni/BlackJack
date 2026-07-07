# 01 — Architecture Overview

## The mental model

This is **not** a single web app. It is **five running processes** that cooperate over HTTP
and WebSockets, plus a PostgreSQL database. They fall into two groups:

```
                          ┌───────────────────────────────────────────────┐
                          │                 "MAIN SERVER"                   │
                          │            (3 independent services)             │
   Browser                │                                                 │
  ┌────────┐   HTTP +     │   ┌──────────────────┐                          │
  │ Player │◀── Socket ──▶│   │ client_interface │  player-facing web app   │
  │  (web) │              │   │   :5000 (→16000) │  login / home / dispatch │
  └────────┘              │   └────────┬─────────┘                          │
       │                  │            │ HTTP                               │
       │ POST /join       │            ▼                                    │
       │ (+ JWT)          │   ┌──────────────────┐      ┌────────────────┐  │
       │                  │   │database_interface│◀────▶│  PostgreSQL    │  │
       │                  │   │   :5001          │ ORM  │   (postgres17) │  │
       │                  │   └────────▲─────────┘      └────────────────┘  │
       │                  │            │ HTTP                               │
       │                  │   ┌────────┴─────────┐                          │
       │                  │   │servers_interface │  game-server-facing API  │
       │                  │   │   :5002 (→16001) │  register / results      │
       │                  │   └────────▲─────────┘                          │
       │                  └────────────┼────────────────────────────────────┘
       │                               │ HTTP (encrypted handshake, JWT results)
       ▼                               │
  ┌──────────────────┐                 │
  │   game_server    │─────────────────┘
  │   :8000          │  real-time Blackjack engine (1..N of these)
  │  (Socket.IO)     │  registers itself + reports results upstream
  └──────────────────┘
```

### Group 1 — "Main Server" (the central back-end)

Despite the name, the `main_server/` directory is **not one server**. It contains **three
separate Flask applications**, each launched as its own process, each with its own port:

| Service | Dir | Default port | Docker port | Role |
|---|---|---|---|---|
| **database_interface** | `main_server/database_interface` | 5001 | (internal only) | The **only** component allowed to talk to PostgreSQL. Exposes a small REST API over the DB. |
| **client_interface** | `main_server/client_interface` | 5000 | 16000 | The **web front-end for players**: serves HTML, handles login/registration, and dispatches players to a game server. |
| **servers_interface** | `main_server/servers_interface` | 5002 | 16001 | The **back-end for game servers**: handles game-server registration and result reporting. |

They share code through a fourth, non-runnable package: **`common`** (data classes, HTTP
helpers, constants — see [doc 03](03-common-module.md)).

### Group 2 — Game server(s)

`game_server/` is a **standalone, independently deployable** process that runs the actual
Blackjack game. The design intent is that you can run **many** of them; `client_interface`
load-balances players across whichever ones are currently registered. Each game server:

1. On startup, **registers itself** with `servers_interface` (so the central system knows it exists and how to reach it).
2. Serves a real-time game over **Socket.IO** to the browsers redirected to it.
3. Reports **round results** (who won/lost how much) back upstream so balances persist.

## Why is it split like this?

This is a textbook **separation-of-concerns / microservices** layout:

- **Single database owner.** Only `database_interface` imports SQLAlchemy and connects to
  Postgres. Every other service that needs data makes an **HTTP call** to it. This keeps DB
  credentials and schema knowledge in one place and lets the rest of the system be ignorant
  of *how* data is stored.
- **Trust boundaries differ.** `client_interface` faces untrusted players; `servers_interface`
  faces semi-trusted game servers (authenticated with a shared secret + per-server keys).
  Keeping them as separate apps means they can have different auth rules and be exposed on
  different ports/hosts.
- **Horizontal scale where it matters.** Game logic is the CPU/connection-heavy part, so
  `game_server` is the piece designed to be replicated. The central services stay singular.

## How the services communicate

| From → To | Transport | Purpose |
|---|---|---|
| Browser → client_interface | HTTP (forms) + Socket.IO | Page loads, login/register, "get my info", "find me a table" |
| Browser → game_server | HTTP `POST /join` (+ JWT) then Socket.IO | Enter the table, then play in real time |
| client_interface → database_interface | HTTP (JSON) | Read/write users, list game servers |
| servers_interface → database_interface | HTTP (JSON) | Persist new game servers, write round results |
| game_server → servers_interface | HTTP (JSON, encrypted) | Self-registration, result reporting |
| database_interface → PostgreSQL | SQLAlchemy / psycopg2 | Actual persistence |

The HTTP-between-services calls all go through one tiny shared helper,
`common/http_requests.py` (`get_request` / `post_request`). See [doc 03](03-common-module.md).

## Repository layout at a glance

```
BlackJack/
├── docker-compose.yml        # Orchestrates postgres + the 3 central services + 1 game server
├── Dockerfile                # App image: installs deps via Poetry
├── Dockerfile-poetry         # Base image "ppython" = python + poetry
├── startup.sh                # Builds the base image then `docker compose up`
├── pyproject.toml            # Poetry config; defines the 4 runnable entry points
├── poetry.lock
├── secret_generator.py       # Generates a Fernet SHARED_SECRET into a .env file
├── API_doc.md                # Author's HTTP API reference
├── database/
│   └── db_create.sql         # Raw SQL schema (reference; ORM also creates tables)
├── common/  (lives under main_server/common)  # Shared dataclasses + HTTP + constants
├── main_server/
│   ├── common/               # shared code (see doc 03)
│   ├── database_interface/   # service 1 — owns the DB (doc 05)
│   ├── client_interface/     # service 2 — player web app (doc 06)
│   └── servers_interface/    # service 3 — game-server API (doc 07)
└── game_server/              # the real-time game engine (doc 08)
    ├── src/
    └── tests/
```

## Naming caveats to internalize early

- **"Central server"** in the code/comments = the main server, specifically `servers_interface`
  (its URL is passed to game servers as `CENTRAL_SERVER_URL`).
- The game server's internal Python package is literally named **`src`** (see
  `pyproject.toml`: `{ include = "src", from = "game_server" }`). So imports look like
  `from src.model.game_structures import ...`.
- Comments are a mix of **English and Italian** (the author is Italian). Both appear
  throughout; they mean the same kind of thing.

Next: [02 — Technology Stack](02-technology-stack.md).
