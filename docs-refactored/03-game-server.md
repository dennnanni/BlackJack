# 03 — Game Server

`game_server/` is the real-time Blackjack engine. You can run **many** of them; each
one registers itself with central and gets players dispatched to it. All game state
(tables, hands, bets) is **in memory**; the only thing a game server persists is its
**outbox** of not-yet-acknowledged round results.

## Startup (`app.py`)

`create_app()`:

1. registers the Flask blueprint (`join.py`) and initializes Socket.IO;
2. **registers with central** — `POST /api/servers/register {host, port, capacity}` —
   with a retry loop (5 attempts, 2 s apart; exits if all fail). This is service
   discovery, and the retry is the first piece of partition tolerance: central may be
   down when the game server boots;
3. starts two daemon threads:
   - **heartbeat** — every `HEARTBEAT_INTERVAL` (5 s) reports
     `{load: <connected players>}`; a 404 response means central no longer knows this
     server (e.g. its registry was reset) and triggers a re-registration;
   - **outbox sender** — see below.

## join.py — the HTTP door

| Route | Behavior |
|---|---|
| `GET /` | informational page ("join through the central server") |
| `POST /join` | form field `token` = the join-JWT minted by central |

`verify_join_token` decodes the token with the `SHARED_SECRET` and rejects it (401)
if invalid/expired, or (403) if its `server_id` claim doesn't match **this** server's
id — a token minted for server 1 opens no doors on server 2.

On success the username and balance **from the token** are stored in the Flask
session, and the game UI (`index.html`) is rendered. The client never supplies its
own identity or balance anywhere — this closed a real hole in the pre-refactor
system, where the browser sent its own `balance` in the Socket.IO `join` event.

## events.py — Socket.IO events

The session written by `/join` is readable inside the socket handlers, so every
event derives the player from `session['username']`.

| Event (in) | Payload | Effect |
|---|---|---|
| `join` | — | seat the player: `TableManager` puts them at a table with space (max 3 per table), or as an **observer** of a running game, or opens a new table. Starts a `GameLoop` thread if the table is ready. A player already seated (page refresh) simply rejoins their room. |
| `bet` | `{amount}` | place the bet; when the last active player has bet, wakes the loop early |
| `player_action` | `{action: hit\|stand\|double}` | applies the action, emits the resulting cards/busts; when every player is done, wakes the loop |
| `disconnect` | — | if the player is *not* mid-round, they are unseated and the load drops. Mid-round players stay: the round auto-stands them on timeout and their result is still reported. |

Events emitted to the table's room: `game_starting`, `place_bets`, `bet_confirmed`,
`no_players_bet`, `initial_cards`, `card_drawn`, `player_busted`, `user_stood`,
`user_doubled`, `player_auto_stand`, `player_action_done`, `dealer_done`,
`round_results` (`{results: [{username, balance_difference}]}`), `error`.

## loop.py — the round state machine

One `GameLoop` thread per active table. Per round:

1. `game_starting`, then `place_bets`; wait up to **35 s** (`BET_WINDOW_SECONDS`) or
   until everyone has bet. Players who didn't bet are excluded from the round; if
   nobody bet, the round is cancelled.
2. Deal two cards to each player, emit `initial_cards`.
3. Wait up to **60 s** (`ACTION_WINDOW_SECONDS`) or until every player stood, busted
   or doubled; whoever is still undecided is **auto-stood**.
4. Dealer draws to 17 (`dealer_done`).
5. `game.determine_result()` computes each player's **balance delta**
   (win = +bet, loss/bust = −bet, push = 0, blackjack beats a non-blackjack 21).
6. **The deltas are enqueued to the outbox first**, then `round_results` is emitted.
   The loop never talks to central directly — delivery is the sender thread's job.
7. Observers become players and the next round starts if anyone is still seated.

## outbox.py + the sender thread — never lose a finished round

The outbox is a tiny SQLite table (`pending(round_id PK, payload, created_at)`) at
`OUTBOX_PATH`. Because the enqueue happens **before** anything else at round end,
a crash of the game server or an unreachable central cannot lose the result: it is
already on disk.

The sender thread loops forever:

```
for each pending entry (oldest first):
    POST /api/servers/results {round_id, results}
    200  -> ack (delete the entry)
    else -> stop, sleep 2 s, retry from the oldest
```

This is **at-least-once delivery**; central's `round_id` ledger turns it into
**exactly-once effect** (see [06](06-distributed-systems.md)). In Docker the outbox
lives on a named volume, so it also survives container restarts.

## game/model.py — the game model

Pure in-memory logic, no I/O — this is the most heavily unit-tested code in the
repo: `Card`, `Deck`, `Hand` (ace worth 11 or 1, multi-ace aware), `User` (name,
balance, hand), `Game` (bets, dealer, results), `Table` (players + observers),
`TableManager` (seating). `Result` comes from `shared/messages.py` — the same class
central parses on the other side of the wire.

## Configuration (`config.py`)

| Variable | Default | Meaning |
|---|---|---|
| `SERVER_HOST` / `SERVER_PORT` | 127.0.0.1 / 8000 | the address **the browser** uses to reach this server; advertised to central at registration |
| `CENTRAL_URL` | http://localhost:5000 | where central lives |
| `SHARED_SECRET` | *(required, from `.env`)* | HS256 key for every JWT |
| `CAPACITY` | 10 | max players, reported at registration |
| `HEARTBEAT_INTERVAL` | 5 s | heartbeat period |
| `OUTBOX_PATH` | `outbox.db` | where unacknowledged results live |
| `SECRET_KEY` | random per boot | Flask session-cookie key |

Next: [04 — Data Model](04-data-model.md).
