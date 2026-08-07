# 09 — Partition-Tolerance Demo (script for the presentation)

One sitting, ~5 minutes, exercises every mechanism in
[06](06-distributed-systems.md): registration retry, heartbeat failure detection,
autonomous gameplay, holder-side lease expiry, durable buffering, at-least-once
delivery and exactly-once application.

Setup: `docker compose up --build`. The compose file defines **two networks** for
exactly this purpose: `blackjack_internal` (game servers ↔ central ↔ postgres) and
`blackjack_frontend` (the browser-facing side of the game servers, listed first so
the published ports route through it). Disconnecting a game server from
`blackjack_internal` therefore severs **only** its link to central — the browser
keeps its live Socket.IO connection: a genuine *partial* partition.

## 1. Baseline

1. Open http://localhost:16000, register a player, log in — balance **1000**.
2. Hit **Play** → the browser lands on a game server (say `localhost:8001`).
3. Play one round (bet, hit/stand). Watch the balance change on the game page, then
   go back to http://localhost:16000 — the balance of record already reflects the
   round: the outbox flushed instantly. `central` logs show the results POST.

## 2. Partition

```bash
docker network disconnect blackjack_internal blackjack-game_server_1-1
```

4. Within ~15 s (`HEARTBEAT_TTL`) the server's heartbeats have gone stale and it is
   out of the dispatch set. Failure detection is a predicate, not a thread, so the
   way to *see* it is step 7: **Play** no longer sends anyone there.
5. **The game page still works — for the length of the lease.** Play a round or two:
   betting, cards, dealer and results all happen locally. The game server logs show
   the sender failing: `[central] sending results for round <uuid> failed ... retrying`.
   Then, once 15 s (`LEASE_TIMEOUT`) have passed without central confirming a
   heartbeat, the page shows **"connection to the central server lost — no new rounds"**
   and the table freezes. Any round already dealt was finished normally. Nobody is
   kicked, nothing is voided: this is the game server refusing to stake money it can
   no longer prove it is allowed to stake
   ([06 §6.7](06-distributed-systems.md#67-handling-the-partition-holder-side-lease-expiry)).
6. Refresh the central home page: the balance of record is **unchanged** — the
   results are parked in the outbox.
7. (Optional, second browser/incognito) Log in as another player and hit **Play**:
   you are dispatched to game server 2 — the dead server is out of the dispatch set.
   With *both* game servers disconnected, Play answers "no game server available".

## 3. Crash during the partition (durability)

```bash
docker restart blackjack-game_server_1-1        # still disconnected? reconnect first killing it:
# or harder: docker kill blackjack-game_server_1-1 && docker start blackjack-game_server_1-1
```

8. The outbox lives on the `gs1_outbox` volume, so the pending rounds survived the
   restart. (The in-memory table is gone — that boundary is documented and accepted;
   *finished* rounds are never lost.)

## 4. Heal

```bash
docker network connect blackjack_internal blackjack-game_server_1-1
```

9. Within a few seconds: the sender flushes (game-server logs), central applies the
   deltas, and the heartbeats resume. The frozen table **unfreezes by itself** — the
   banner clears and a new betting round opens, with no reload and nobody
   re-dispatched. Hit **Play** and the server is dispatchable again, with no recovery
   logic anywhere. Refresh the central
   home page — the balance of record **converged** to exactly
   `1000 + Σ(deltas of every round played)`, including the ones played mid-partition.

## 5. Idempotency (no double-money)

Replay a delivery by hand — mint a server token and send the same `round_id` twice:

```bash
docker compose exec central poetry run python - <<'EOF'
import time, jwt, requests
from central_server.config import SHARED_SECRET
now = int(time.time())
tok = jwt.encode({'typ': 'server', 'server_id': 1, 'iat': now, 'exp': now+60},
                 SHARED_SECRET, algorithm='HS256')
body = {'round_id': 'demo-duplicate', 'results': [{'username': '<YOUR-USER>', 'balance_difference': 100}]}
for i in range(2):
    r = requests.post('http://localhost:5000/api/servers/results', json=body,
                      headers={'Authorization': f'Bearer {tok}'})
    print(i + 1, r.status_code, r.json())
EOF
```

Both calls return `200 {success: true}` — but the balance moved **once** (+100, not
+200): the second delivery hit the `applied_round` ledger. That closes the loop:
at-least-once delivery, exactly-once effect.

## 6. One account, one table (no double-spend)

While the player from step 2 is still seated, open a second tab on
http://localhost:16000, log in as the **same** account and hit **Play**: the home
page answers *"you are already seated at a table"*. The seat claim
([06 §6.6](06-distributed-systems.md#66-one-account-one-table-the-seat-lease))
refused it — otherwise the same balance snapshot would be staked at two tables at
once and the balance of record would reconcile to a number neither table ever saw.

Now close the game tab and wait one heartbeat (~5 s): the game server stops listing
that player, central releases the seat, and **Play** works again. Nothing had to
time out, and no explicit "leave" message had to survive the tab being closed.

**The two timeouts are what make step 2 safe.** Central only reassigns a silent
server's seats after `SEAT_TAKEOVER_TTL` (30 s), while the game server has stopped
starting rounds after `LEASE_TIMEOUT` (15 s). So during a partition the player is
already frozen on game server 1 *before* central would let them sit down at game
server 2: the takeover is not a guess that the server crashed, it is safe either way.
Worth watching the clock during the demo — freeze at ~15 s, seat released at ~30 s.
