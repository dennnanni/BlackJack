# 06 — Distributed-Systems Mechanisms

This is the graded core: five cooperating mechanisms, none heavy, that together give
horizontal scaling, failure detection and **network-partition tolerance** with
**eventual consistency**.

## 6.1 Service discovery via registration (with retry)

On startup a game server announces itself:

```
POST /api/servers/register  {host, port, capacity}
Authorization: Bearer <JWT signed with SHARED_SECRET>
```

Central inserts a `gameserver` row and returns the assigned `server_id`. The call is
retried (5 attempts, 2 s apart) because central may itself be down or partitioned at
boot; if the registry is ever reset while the server runs, a 404 on heartbeat makes
it re-register. Central never needs a pre-provisioned list of game servers.

## 6.2 Failure detection via heartbeats

Every 5 s each game server reports:

```
POST /api/servers/heartbeat  {load: <connected players>}
```

Central stamps `last_seen = now` and stores the load. **Liveness is then a pure
predicate**: a server is live iff `last_seen ≥ now − HEARTBEAT_TTL` (15 s = 3
intervals, forgiving lost beats). There is no "mark dead" write anywhere that could
itself fail — a crashed server just stops refreshing its timestamp and silently
falls out of the dispatch set; when heartbeats resume it is eligible again with zero
recovery logic. The **reaper** thread logs these offline/online transitions so
failure detection is observable, and prunes old ledger entries.

## 6.3 Load-aware dispatch

`dispatcher.pick_server()` = the **least-loaded** among live servers with
`load < capacity` (least-connections balancing). The load figure comes from the
heartbeats — reported by the one process that actually knows it — not from a
join-table count maintained at a distance (the old design's `userserver` table was
never written to, so its counts were always 0).

## 6.4 Partition tolerance: the durable outbox

When a round finishes, the game server:

1. generates a **UUID4 `round_id`**;
2. **writes `{round_id, results}` to an on-disk SQLite outbox** — before notifying
   players, before anything;
3. a **sender thread** delivers pending entries to
   `POST /api/servers/results` and deletes each one **only on an HTTP 200**;
   on any failure it backs off (2 s) and retries forever.

Consequences:

- **Central down / network partitioned?** Rounds keep being played and settled
  locally; their results pile up in the outbox and flush after the heal.
- **Game server crashes mid-partition?** The outbox is on disk (a Docker volume in
  compose), so the results are still there when it restarts.
- The one thing a partition blocks is **new joins** — minting a join token needs
  central. That is the deliberate CP/AP boundary: identity and money-of-record stay
  consistent; gameplay stays available.

## 6.5 Exactly-once effect: the idempotency ledger

Delivery above is *at-least-once*, so central must tolerate duplicates:

```python
if session.get(AppliedRound, round_id):
    return success            # already applied: ACK again, change nothing
for r in results:
    user.balance += r.balance_difference   # additive deltas
session.add(AppliedRound(round_id=round_id, ...))
session.commit()              # ledger + balances in ONE transaction
```

At-least-once delivery + idempotent receiver = **effectively exactly once**. Because
the ledger insert and the balance updates share a transaction, even two *concurrent*
deliveries of the same round cannot double-apply — the second dies on the primary
key and its retry hits the already-applied path. And because deltas are additive,
ordering across rounds doesn't matter either.

## The overdraft note (bounded inconsistency)

During a partition a player keeps betting against the balance captured in their join
token, so the balance of record lags reality and could in principle be overdrawn.
This is the accepted AP trade-off, and it is **bounded**: a player sits at one game
server, cannot join another during the partition (joins need central), so there is
no concurrent double-spend across servers, and all deltas reconcile on heal.

## Checklist (for the write-up)

- [x] Horizontal scaling / replicas — N game servers, one central
- [x] Service discovery & registration — with boot-time retry and re-registration
- [x] Failure detection — heartbeats + TTL predicate + reaper visibility
- [x] Load-aware dispatch — least-connections over live servers
- [x] **Partition tolerance** — autonomous gameplay + durable on-disk outbox
- [x] **Eventual consistency** — additive deltas reconcile after heal
- [x] **Idempotency / exactly-once effect** — `round_id` ledger, transactional
- [x] Authentication across trust boundaries — signed, expiring, server-bound tokens

See [09 — Partition-Tolerance Demo](09-partition-demo.md) for the script that
exercises all of this in one sitting.
