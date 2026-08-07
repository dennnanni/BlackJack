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
     `{players: [<usernames seated here>]}`; central derives the load from it and
     renews those players' seat leases, so a player who leaves is unseated centrally
     within one heartbeat. A 404 response means central no longer knows this server
     (e.g. its registry was reset) and triggers a re-registration;
   - **outbox sender** — see below.

The game server also tracks **when central last confirmed it** (a 200 on register or
heartbeat, measured on the local monotonic clock). That is its *lease*: while it is
valid the server may keep staking its players' balances, and when it expires
(`LEASE_TIMEOUT`, 15 s) the game loop freezes new rounds — see
[06 §6.7](06-distributed-systems.md#67-handling-the-partition-holder-side-lease-expiry).

## join.py — the HTTP door

| Route | Behavior |
|---|---|
| `GET /` | the table page if this browser has a session here, otherwise an informational page ("join through the central server") |
| `POST /join` | form field `token` = the join-JWT minted by central; **redirects to `GET /`** |
| `POST /leave` | give up the seat and go back to central (`CENTRAL_PUBLIC_URL`). A stake already on the table is **forfeited** — the round is still played out and settled, so the loss reaches central like any other result. POST, not a link: a prefetched GET must never throw a player off their table. |

`verify_join_token` decodes the token with the `SHARED_SECRET` and rejects it (401)
if invalid/expired, or (403) if its `server_id` claim doesn't match **this** server's
id — a token minted for server 1 opens no doors on server 2.

On success the username and balance **from the token** are stored in the Flask
session. The client never supplies its own identity or balance anywhere — this
closed a real hole in the pre-refactor system, where the browser sent its own
`balance` in the Socket.IO `join` event.

### Reloading the page is always safe

A join token is single-use and short-lived, so the table page must not *be* the
response to `POST /join`: F5 would re-submit a spent token and answer with an error
where the game used to be. Hence **POST/redirect/GET** — the browser ends up on `/`,
where reloading is an ordinary GET rendered from the session. A re-submitted stale
token is not an error either: a browser that already holds a session here was let in
by a valid token once, so it is redirected to its table.

The reload then costs nothing but the events the socket missed, and those are
replayed on reconnect (`_resume`): the board, the phase (`place_bets` if the betting
window is still open and you have not bet, `turn_started` if the loop is waiting on
*you*) and the freeze banner if the lease has expired. The balance shown is the one
the table is playing with, not the older snapshot the token carried.

## events.py — Socket.IO events

The session written by `/join` is readable inside the socket handlers, so every
event derives the player from `session['username']`.

| Event (in) | Payload | Effect |
|---|---|---|
| `join` | — | seat the player: `TableManager` puts them at a table with space (max 3 per table), or as an **observer** of a running game, or opens a new table. Starts a `GameLoop` thread if the table is ready. A player already seated (page refresh) simply rejoins their room and is replayed the current state of the round. |
| `sit_out` | `{sitting_out}` | stop (or resume) being dealt in. A player sitting out is not counted by `all_players_have_bet`, so the table deals as soon as the players who *are* playing have bet instead of sitting through the whole betting window. The flag can be set at any time but only takes effect at a round boundary. |
| `bet` | `{amount}` | opt into the round by staking `amount`; when the last active player has bet, wakes the loop early. Skip it and you simply sit the round out — you stake nothing. |
| `player_action` | `{action: hit\|stand\|double}` | applies the action **only if it is your turn** (the loop hands the table to one player at a time); emits the resulting cards/busts. A plain `hit` keeps your turn; `stand`, `double` or a bust ends it and the loop moves to the next player. |
| `disconnect` | — | if the player is *not* mid-round, they are unseated: the load drops and the next heartbeat no longer lists them, which releases their seat at central so they can play again elsewhere. Mid-round players stay: the round auto-stands them on timeout and their result is still reported. |

Events emitted to the table's room: `game_starting`, `place_bets`, `bet_confirmed`,
`no_players_bet`, `initial_cards`, `turn_started` (`{user}` — whose turn it is now),
`card_drawn`, `player_busted`, `user_stood`, `user_doubled`, `player_auto_stand`,
`dealer_turn`, `dealer_card` (`{card, cards}` — one per card as the dealer draws),
`dealer_done`, `round_results` (`{results: [...], next_round_in}`), `error`.

## loop.py — the round state machine

One `GameLoop` thread per active table. It keeps running for as long as anyone is
seated, playing one round after another **on its own** — a finished round (or an
empty one) never needs a page reload. Per round:

1. `game_starting`, then `place_bets`; wait up to **35 s** (`BET_WINDOW_SECONDS`) or
   until every seated player has bet. Betting is **opt-in**: players who didn't bet
   are excluded from the round and stake nothing. If nobody bet, the loop emits
   `no_players_bet` and simply offers a fresh betting round (it does **not** stop).
2. Deal two cards to each player who bet **and the dealer's upcard** (face up, no
   hole card), emit `initial_cards` (`{hands, dealer_cards}`).
3. **Turn by turn**, the loop hands the table to one player at a time: it emits
   `turn_started {user}` and waits up to **30 s** (`TURN_WINDOW_SECONDS`) for that
   player to `stand`, `double` or bust (a `hit` that doesn't bust keeps their turn).
   A hand already worth 21 is stood automatically; a player who runs out the clock is
   **auto-stood**. Only then does the next player's turn begin.
4. Dealer draws to 17 **from the upcard**, revealing **one card at a time** (`dealer_turn`, then a
   `dealer_card` per draw with a short delay between) and finally `dealer_done`.
5. `game.determine_result()` computes each player's **balance delta**
   (win = +bet, loss/bust = −bet, push = 0, blackjack beats a non-blackjack 21).
6. **The deltas are enqueued to the outbox first**, then `round_results` is emitted.
   The loop never talks to central directly — delivery is the sender thread's job.
7. The loop **pauses (`ROUND_RESULT_DELAY`, ~12 s)** so players can take in the
   outcome and the final hands, then observers become players and it starts the
   next round automatically if anyone is still seated.

The round is deliberately paced so it can be watched rather than flashing past:
`PRE_DEALER_DELAY`, `DEALER_DRAW_DELAY` (between dealer cards), `POST_DEALER_DELAY`
and `ROUND_RESULT_DELAY` are the tunable knobs, and the loop paces itself with
`socketio.sleep()` (safe under the server's threading async mode).

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
