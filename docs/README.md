# BlackJack — Project Documentation

Welcome. This documentation set is written for a developer who is **new to this codebase**
but comfortable with Python. By the end you should understand *what* the project is, *how*
the pieces fit together, *why* they are split the way they are, and *where* to start when you
want to implement something new.

> **What is this project?**
> A **multiplayer, online Blackjack game** built as a small **distributed system**.
> Players use a web browser to register/log in, then are dispatched to one of potentially
> many **game servers** that run the actual card game in real time over WebSockets.
> A **central back-end** (split into three independent services) handles accounts,
> balances, and the registry of available game servers.

## How to read these docs

Read them roughly in order. Each builds on the previous one.

| # | Document | What it covers |
|---|----------|----------------|
| 01 | [Architecture Overview](01-architecture.md) | The big picture: the services, how they talk, why it's split this way. **Start here.** |
| 02 | [Technology Stack](02-technology-stack.md) | Every library/tool used and the role it plays. |
| 03 | [The Common Module](03-common-module.md) | Shared data structures and helpers used by all back-end services. |
| 04 | [Data Model & Database](04-data-model.md) | PostgreSQL schema, the SQLAlchemy ORM, and the data-access layer. |
| 05 | [Main Server: database_interface](05-database-interface.md) | The only service that touches the database. |
| 06 | [Main Server: client_interface](06-client-interface.md) | The player-facing web app (login, home, dispatch). |
| 07 | [Main Server: servers_interface](07-servers-interface.md) | The endpoint that game servers register and report results to. |
| 08 | [The Game Server](08-game-server.md) | The real-time Blackjack engine. The most complex part. |
| 09 | [Security & Encryption](09-security.md) | Password hashing, Fernet encryption, JWT tokens — all in one place. |
| 10 | [End-to-End Flows](10-flows.md) | Step-by-step walkthroughs of every important user journey. |
| 11 | [Running & Developing Locally](11-running-locally.md) | Docker, Poetry, environment variables, tests. |
| 12 | [Known Issues & Rough Edges](12-known-issues.md) | Honest list of bugs, dead code, and inconsistencies to be aware of. |
| 13 | [How to Start Contributing](13-getting-started.md) | Practical recipes for common changes. |

There is also the original [`API_doc.md`](../API_doc.md) in the repo root, which is the
author's HTTP API reference. Doc 05 and 07 expand on it.

> 🔧 **Planning a rewrite?** See [REFACTOR_PLAN.md](REFACTOR_PLAN.md) — a phased plan to
> collapse the three central services into one app, cut the crypto down to a single shared
> secret, and add network-partition tolerance (heartbeats + durable result outbox + idempotent,
> eventually-consistent balances). Docs 01–13 describe the system **as it is today**; the
> refactor plan describes where it's **going**.

## One-paragraph summary

A browser talks to **`client_interface`** (Flask web app). Login/registration data is
forwarded to **`database_interface`**, the single owner of the **PostgreSQL** database.
When a player hits "Play", `client_interface` asks `database_interface` for the list of
running **game servers**, picks the least-loaded one, mints a **JWT** for the player, and
redirects the browser to that game server. Each **`game_server`** is an independent process
that, on startup, **registers itself** with **`servers_interface`** (encrypting the handshake
with a shared secret). The game server runs Blackjack rounds in real time via **Socket.IO**,
and when a round ends it reports each player's balance change back through `servers_interface`,
which writes it to the database via `database_interface`.
