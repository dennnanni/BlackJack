# 09 — Partition-Tolerance Demo (script for the presentation)

One sitting, ~5 minutes, exercises every mechanism in
[06](06-distributed-systems.md): registration retry, heartbeat failure detection,
autonomous gameplay, durable buffering, at-least-once delivery and exactly-once
application.

Setup: `docker compose up --build`, then find the compose network name
(`docker network ls`, it is `<project>_default`, e.g. `blackjack_default`).

## 1. Baseline

1. Open http://localhost:16000, register a player, log in — balance **1000**.
2. Hit **Play** → the browser lands on a game server (say `localhost:8001`).
3. Play one round (bet, hit/stand). Watch the balance change on the game page, then
   go back to http://localhost:16000 — the balance of record already reflects the
   round: the outbox flushed instantly. `central` logs show the results POST.

## 2. Partition

```bash
docker network disconnect blackjack_default blackjack-game_server_1-1
```

4. Within ~15 s central's logs show the failure detection:
   `[reaper] game server 1 missed its heartbeats: considered offline...`
5. **The game page still works.** Play one or two full rounds — betting, cards,
   dealer, results all happen locally. The game server logs show the sender failing:
   `[central] sending results for round <uuid> failed ... retrying`.
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
docker network connect blackjack_default blackjack-game_server_1-1
```

9. Within a few seconds: the sender flushes (game-server logs), central applies the
   deltas, and `[reaper] game server 1 is back online` appears. Refresh the central
   home page — the balance of record **converged** to exactly
   `1000 + Σ(deltas of every round played)`, including the ones played mid-partition.

## 5. Idempotency (no double-money)

Replay a delivery by hand — mint a server token and send the same `round_id` twice:

```bash
docker compose exec central poetry run python - <<'EOF'
import time, jwt, requests
from central_server.config import SHARED_SECRET
now = int(time.time())
tok = jwt.encode({'server_id': 1, 'iat': now, 'exp': now+60}, SHARED_SECRET, algorithm='HS256')
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
