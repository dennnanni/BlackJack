# 06 — Distributed-Systems Mechanisms

This is the graded core: six cooperating mechanisms, none heavy, that together give
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
POST /api/servers/heartbeat  {players: [<usernames seated here>]}
```

Central stamps `last_seen = now`, stores `load = len(players)`, and renews those
players' seat leases (§6.6) — one message, because liveness, load and seat
ownership are all facts only the game server knows. **Liveness is then a pure
predicate**: a server is live iff `last_seen ≥ now − HEARTBEAT_TTL` (15 s = 3
intervals, forgiving lost beats). There is no "mark dead" write anywhere that could
itself fail — a crashed server just stops refreshing its timestamp and silently
falls out of the dispatch set; when heartbeats resume it is eligible again with zero
recovery logic — no thread is involved in the decision. The **reaper** thread only
prunes old ledger entries.

## 6.3 Load-aware dispatch

Dispatch picks the **least-loaded** among live servers with
`load < capacity` (least-connections balancing). The load figure comes from the
heartbeats' player list — reported by the one process that actually knows it — not from a
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
for r in results:             # additive delta, applied by the DB itself
    session.execute(update(User).where(User.username == r.username)
                    .values(balance=User.balance + r.balance_difference))
session.add(AppliedRound(round_id=round_id, ...))
session.commit()              # ledger + balances in ONE transaction
```

At-least-once delivery + idempotent receiver = **effectively exactly once**. Because
the ledger insert and the balance updates share a transaction, even two *concurrent*
deliveries of the same round cannot double-apply — the second dies on the primary
key and its retry hits the already-applied path. And because deltas are additive,
ordering across rounds doesn't matter either.

Two details that idempotency alone does **not** buy, and that are handled here:

- **No lost updates.** Each delta is one SQL statement — `SET balance = balance + d`
  — evaluated by the database under its own row lock. Reading the balance into
  Python, adding, and writing it back would be a read-modify-write: two *different*
  rounds of the same player, delivered concurrently by two game servers draining
  their outboxes independently, would each read the same pre-value and one delta
  would vanish. The ledger would not notice — the round ids differ, so both are
  legitimately "applied once".
- **Ledger retention vs. retry horizon.** Entries are pruned after 7 days while the
  outbox retries indefinitely, so a partition lasting longer than the retention
  window could in principle re-admit a duplicate. The two constants must be read
  together; 7 days is the assumed upper bound on any partition worth reconciling.

## 6.6 One account, one table: the seat lease

Idempotency makes each round land exactly once, but nothing in it stops the *same
player* from generating rounds on two servers at once. Dispatch is what must
prevent that: the join token carries a **balance snapshot**, so an account seated at
two tables would stake the same money twice and reconcile to a balance neither table
ever saw.

The `seat` table makes the constraint explicit, with `username` as the primary key:

```
POST /play → take_seat(username, chosen_server, HEARTBEAT_TTL)
             ├─ no seat            → insert (a concurrent /play loses on the PK)
             ├─ seat on this server→ refresh (re-dispatch to the same table is fine)
             ├─ seat on a LIVE one → refuse: "you are already seated at a table"
             └─ seat on a DEAD one → take it over
```

Three properties worth noting:

- **The mutual exclusion is the database's, not the application's.** Two simultaneous
  `POST /play` requests for one account do not need a lock in Flask; the primary-key
  conflict decides, and the loser is simply refused. This matters because central may
  itself be run as several replicas.
- **The lease is renewed by the party that knows.** Seats are not released on a timer
  by central, and not by an explicit "leave" call that a crashing browser would never
  send: each heartbeat carries the *complete* seat list of its sender, so a player
  who closed the tab is unseated within one heartbeat. A freshly claimed seat is
  protected for `SEAT_GRACE` (30 s) so the player still travelling from the dispatch
  page to `/join` is not evicted by a heartbeat that predates their arrival.
- **A dead owner does not hold seats hostage.** Honouring a seat whose server has
  stopped heartbeating would lock those players out for good after a crash. The seat
  is therefore taken over — which is safe when the server truly crashed, and is the
  deliberate soft spot during a *partition*: see below.

## The overdraft note (bounded inconsistency)

During a partition a player keeps betting against the balance captured in their join
token, so the balance of record lags reality and could in principle be overdrawn.
This is the accepted AP trade-off, and it is **bounded** — the bound being the seat
lease of §6.6: one account is seated at one table, so the exposure of a partition of
duration *T* is at most

```
max_overdraft ≈ (rounds per second at one table) × T × (max bet)
```

with no cross-server multiplier, because a second dispatch is refused while the
player's seat is held.

The one case where that bound is weakened is the *partial* partition the demo
stages: a game server that keeps its players but loses the link to central stops
heartbeating, its seats are eventually treated as free, and the player could be
dispatched to a second server while still playing on the first. This is the price of
the "a crashed server must not lock its players out" rule, and it is the honest
statement of the trade-off: central cannot distinguish a crash from a partition —
that is precisely the impossibility the whole design is arranged around. Making the
seat unforgeable during a partition would require fencing it with an epoch that only
the reachable side can advance, i.e. genuine consensus, which is deliberately out of
scope here.

## Checklist (for the write-up)

- [x] Horizontal scaling / replicas — N game servers, one central
- [x] Service discovery & registration — with boot-time retry and re-registration
- [x] Failure detection — heartbeats + TTL predicate, evaluated at dispatch time
- [x] Load-aware dispatch — least-connections over live servers
- [x] **Partition tolerance** — autonomous gameplay + durable on-disk outbox
- [x] **Eventual consistency** — additive deltas reconcile after heal
- [x] **Idempotency / exactly-once effect** — `round_id` ledger, transactional
- [x] **Mutual exclusion across the cluster** — one seat per account, leased by heartbeat
- [x] Authentication across trust boundaries — signed, expiring, server-bound tokens

See [09 — Partition-Tolerance Demo](09-partition-demo.md) for the script that
exercises all of this in one sitting.
