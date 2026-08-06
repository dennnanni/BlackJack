# BlackJack — Documentation

This documentation set describes the system as it is today. (An earlier
four-service architecture and the plan that replaced it live in git history,
before the `docs/` consolidation.)

> **What is this project?**
> A **multiplayer, online Blackjack game** built as a small **distributed system**.
> Players use a web browser to register/log in on a **central server**, then are
> dispatched to one of potentially many **game servers** that run the card game in
> real time over WebSockets. The system is explicitly designed to tolerate **network
> partitions** between the game servers and the central server.

## How to read these docs

| # | Document | What it covers |
|---|----------|----------------|
| 01 | [Architecture](01-architecture.md) | The two-process design, how the pieces talk, CAP positioning. **Start here.** |
| 02 | [Central Server](02-central-server.md) | Accounts, login, dispatch, the game-server API, housekeeping. |
| 03 | [Game Server](03-game-server.md) | The real-time Blackjack engine, join flow, game loop, outbox. |
| 04 | [Data Model](04-data-model.md) | PostgreSQL schema, the ORM, and the game server's local outbox store. |
| 05 | [Security](05-security.md) | The two crypto mechanisms: password hashing and shared-secret JWTs. |
| 06 | [Distributed-Systems Mechanisms](06-distributed-systems.md) | The graded core: discovery, failure detection, partition tolerance, eventual consistency, idempotency. |
| 07 | [End-to-End Flows](07-flows.md) | Step-by-step walkthroughs of every user journey. |
| 08 | [Running & Testing](08-running-and-testing.md) | Docker, Poetry, environment variables, the test suite. |
| 09 | [Partition-Tolerance Demo](09-partition-demo.md) | The scripted demo that shows the whole story end to end. |

## One-paragraph summary

A browser talks to the **central server** (one Flask app) to register, log in and see
its balance. When the player hits **Play**, central picks the least-loaded *live* game
server (liveness comes from heartbeats), mints a short-lived **join token** (a JWT
carrying the username, the balance, and the id of the chosen server), and the browser
posts it to that game server's `/join`. The **game server** verifies the token with
the same shared secret, seats the player at a table, and runs Blackjack rounds over
**Socket.IO**. When a round ends, its results are written to an **on-disk outbox**
first and then delivered to central with retries; central applies them **idempotently**
(deduplicated by `round_id`), so balances converge exactly once even across crashes,
retries and network partitions.
