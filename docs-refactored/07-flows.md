# 07 — End-to-End Flows

## Registration & login

```
Browser                          Central
  │ POST /register {u, p}          │
  │────────────────────────────▶  │ generate salt, PBKDF2-hash p,
  │                                │ INSERT user (balance 1000)
  │ ◀── 302 /login ────────────── │
  │ POST /login {u, p}             │
  │────────────────────────────▶  │ fetch user, hash attempt with stored
  │                                │ salt, compare; Flask-Login session
  │ ◀── 302 /user/u  + cookie ─── │
  │ GET /user/u                    │
  │ ◀── home.html (balance is ─── │   ... rendered server-side, no sockets
```

## Dispatch & join

```
Browser                Central                              Game server 2
  │ POST /play            │                                     │
  │─────────────────────▶ │ pick least-loaded live server (=2)  │
  │                       │ mint join-JWT {sub, balance,        │
  │                       │                server_id: 2, exp+120}│
  │ ◀─ dispatch.html ──── │                                     │
  │    (auto-submitting form)                                   │
  │ POST http://host2:port2/join {token} ──────────────────────▶│ verify sig
  │                                                             │ server_id == 2? ✓
  │                                                             │ session[u, balance]
  │ ◀── index.html (game UI) ───────────────────────────────────│
  │ Socket.IO connect (cookie carries the session) ────────────▶│
  │ emit join  ────────────────────────────────────────────────▶│ seat at a table,
  │ ◀── joined {table_id, is_player} ───────────────────────────│ start GameLoop
```

If no live game server exists (all partitions/down/full), `/play` re-renders home
with an error — the player's money is untouched.

## One round

```
GameLoop (server thread)                     Players (via Socket.IO)
  │ emit game_starting, place_bets              │
  │ wait ≤35s ◀───────────────── emit bet {amount}
  │ deal 2 cards each, emit initial_cards       │
  │ wait ≤60s ◀───────────── emit player_action {hit|stand|double}
  │   (auto-stand whoever is left)              │
  │ dealer draws to 17, emit dealer_done        │
  │ compute results (deltas)                    │
  │ OUTBOX.enqueue(round_id, results)  ← on disk *before* anything else
  │ emit round_results ────────────────────────▶ UI updates balances
```

## Result delivery (the happy path)

```
Sender thread                          Central
  │ POST /api/servers/results            │
  │   {round_id, results}, Bearer JWT ─▶ │ round_id in ledger? no →
  │                                      │ apply deltas + insert ledger row
  │ ◀── 200 {success} ─────────────────  │ (one transaction)
  │ outbox.ack(round_id)                 │
```

## Result delivery (partition, crash, heal)

```
  │ POST /results ──✗ (timeout: partition!)     rounds keep being played,
  │ sleep 2s, retry ──✗ ...                     more entries accumulate
  │            [game server may even crash and restart: outbox is on disk]
  │ ...link heals...
  │ POST /results {round_id A} ─▶ 200 → ack
  │ POST /results {round_id B} ─▶ 200 → ack     balances converge
  │ POST /results {round_id B} ─▶ 200 (duplicate: ledger hit, no re-apply)
```

## Disconnect

- Player closes the tab **between rounds** → the `disconnect` handler unseats them;
  the next heartbeat reports the lower load.
- Player closes the tab **mid-round** → they stay seated for the round, the loop
  auto-stands them at the action timeout, their delta is still computed, enqueued and
  delivered; they are unseated on the next disconnect-aware pass (or rejoin and
  continue).
- Player refreshes the page → same session cookie, `join` finds them already seated
  and reattaches to the same table room.

Next: [08 — Running & Testing](08-running-and-testing.md).
