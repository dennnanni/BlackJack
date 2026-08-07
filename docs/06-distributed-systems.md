# 06 — Distributed-Systems Mechanisms

This is the graded core: seven cooperating mechanisms, none heavy, that together give
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
- **New joins** are blocked outright — minting a join token needs central. That is
  the deliberate CP/AP boundary: identity and money-of-record stay consistent.
- Gameplay stays available, but **not indefinitely**: after `LEASE_TIMEOUT` the
  server stops starting new rounds (§6.7). Autonomy here is bounded on purpose —
  that bound is what keeps the balance of record safe.

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
POST /play → take_seat(username, chosen_server, SEAT_TAKEOVER_TTL)
             ├─ no seat            → insert (a concurrent /play loses on the PK)
             ├─ seat on this server→ refresh (re-dispatch to the same table is fine)
             ├─ seat on a LIVE one → refuse: "you are already seated at a table"
             └─ seat on a DEAD one → take it over
```

Three properties worth noting:

- **The mutual exclusion is the database's, not the application's.** Two simultaneous
  `POST /play` requests for one account do not need a lock in Flask; the loser is
  simply refused. This matters because central may itself be run as several replicas.
  Note *which* database mechanism decides on *which* path, because it is not one
  mechanism: an account with **no** seat is arbitrated by the **primary key** — both
  inserts race, one gets an `IntegrityError` and is refused. An account whose seat is
  being **taken over** from a dead server is a read-modify-write (read the row, see a
  dead owner, rewrite `server_id`), and there the primary key decides nothing at all:
  both updates would find the row present and both would commit, seating one account
  at two tables. That path therefore reads the row **`FOR UPDATE`**, so the second
  claim blocks and then sees the first one's write. A locking read on one path, a
  uniqueness constraint on the other — the constraint alone is not enough.
- **The lease is renewed by the party that knows.** Seats are not released on a timer
  by central, and not by an explicit "leave" call that a crashing browser would never
  send: each heartbeat carries the *complete* seat list of its sender, so a player
  who closed the tab is unseated within one heartbeat. A freshly claimed seat is
  protected for `SEAT_GRACE` (30 s) so the player still travelling from the dispatch
  page to `/join` is not evicted by a heartbeat that predates their arrival.
- **A silent owner does not hold seats hostage.** Honouring a seat whose server has
  stopped heartbeating would lock those players out for good after a crash, so after
  `SEAT_TAKEOVER_TTL` the seat is taken over. On its own that would be a *guess* that
  the server crashed rather than being partitioned — §6.7 is what makes it sound.

## 6.7 Handling the partition: holder-side lease expiry

§6.6 leaves one hole, and it is the interesting one. Central sees **silence** from a
game server, and a crashed server and a partitioned-but-perfectly-healthy one send
exactly the same silence. Whatever central then does is a guess:

- honour the seat forever → one crash locks those players out permanently;
- give the seat away → the partitioned server is *still running rounds* for a player
  who has now been re-dispatched elsewhere, and the same balance is staked twice.

That dilemma is not solvable by choosing a smarter timeout on central's side, because
the information central is missing does not exist on central's side. It is solvable
by noticing what a join token really is: **a lease**. Central let this game server
move a player's money on the assumption that it can hear from us, so that permission
has an expiry — and a lease only the grantor tracks is not a lease, it is a hope. So
the holder expires it too:

```
game server, before starting each round AND again before dealing:
    lease_valid()  ==  (time since central last ACKed a heartbeat) < LEASE_TIMEOUT
    if not valid → cancel/freeze, re-check, resume when it returns
```

**The safety condition is an inequality**, and it is the whole argument:

```
LEASE_TIMEOUT (15 s, game server)  <  SEAT_TAKEOVER_TTL (30 s, central)
```

The holder gives up strictly before the grantor reassigns, so there is no instant at
which two servers both believe they may stake the same player's balance. The 15 s
margin covers one in-flight heartbeat plus clock-rate drift; note that the game
server measures **elapsed time on its own monotonic clock**, so no clock
synchronisation between hosts is assumed anywhere in this design.

### Where the check has to happen (the granularity trap)

An inequality between two *timeouts* only protects anything if the check happens at
the instant the protected action occurs. Checking the lease once at the top of each
round does **not** qualify, and this is subtle enough to be worth stating plainly:

```
BET_WINDOW 35 s + 3 × TURN_WINDOW 30 s + dealer + pacing  ≈  140 s per round
```

A round is an order of magnitude longer than the 15 s gap between the two constants.
So a lease checked only at the round boundary, and valid at that moment, would still
let the table accept bets at *t = 30 s* — i.e. staking money 30 s after last contact,
having declared its own limit to be 15 s, at the very moment central becomes willing
to hand those seats away. The inequality would hold on paper and be violated in fact:
**the constants were never the problem, the granularity was.**

The fix is to check again at the last instant before the stakes become real — the
**deal**. Bets collected during the window are not yet commitments, so a round
cancelled between the window and the deal costs nobody anything (no cards shown, no
result settled, nothing to void), and after it the outer loop freezes the table
normally. The choke point is singular on purpose: every path that commits money runs
through the deal, so one guard covers them all rather than one per entry point.

With the check there, "this server never *begins* staking while its lease is dead"
is true instant-by-instant, and the inequality means what it says. What remains
outstanding across a takeover is at most the *already dealt* round — money committed
while the lease was still valid — which is exactly the bounded exposure the section
below quantifies, and exactly why finishing a dealt hand is still the right call.

Freezing is deliberately gentle, because the point is to protect the money, not to
punish the players:

- a **dealt** round is always finished — settled and written to the outbox as usual.
  Aborting a dealt hand is the one thing worse than continuing, and its exposure is a
  single round;
- a round that has only reached **betting** is cancelled instead, since a bet is not
  a stake until the cards go down: nothing is voided because nothing had happened yet.
  This is the `deal`-time check above, and it is what keeps "dealt" the *only* thing
  that can still be outstanding when the lease dies;
- the **next** round is held back. The table, the seats and the sockets stay up;
  the UI shows "connection to the central server lost — no new rounds";
- when a heartbeat is ACKed again the loop emits `lease_restored` and play resumes by
  itself. No kick, no re-dispatch, no page reload, nothing voided.

The alternative worth naming (and rejecting) is **fencing**: give each seat an epoch
and have central discard results carrying a stale one. It is the standard answer when
the fenced-off writes are garbage from a zombie leader — but here they are the honest
record of games that really happened, and since stakes are never debited up front,
discarding them would take back a winner's winnings while leaving a loser's money
untouched. That trades a money bug for a fairness bug. Freezing keeps every played
round valid.

## The overdraft note (bounded inconsistency)

During a partition a player keeps betting against the balance captured in their join
token, so the balance of record lags reality and could in principle be overdrawn.
This is the accepted AP trade-off, and after §6.7 it is bounded by a **constant**:

```
max_overdraft ≈ (rounds playable within LEASE_TIMEOUT) × (max bet)
```

— note what is *not* in that formula. There is no partition duration *T*: the
exposure stops growing the moment the lease expires, however long the link stays
down. And there is no cross-server multiplier, because a second dispatch is refused
while the seat is held, and once it is given away the old server has already stopped
staking. What remains is genuinely irreducible without debiting stakes up front,
which would mean a synchronous round trip to central per bet — i.e. giving up
partition tolerance altogether, which is the property the whole design exists to
demonstrate.

The honest scope note: the seat's authority lives in a single Postgres behind a
single central process. **Replicating central** is where this design would need
consensus — a monotonic, partition-safe source for seat ownership — and that is
deliberately out of scope here.

## Checklist (for the write-up)

- [x] Horizontal scaling / replicas — N game servers, one central
- [x] Service discovery & registration — with boot-time retry and re-registration
- [x] Failure detection — heartbeats + TTL predicate, evaluated at dispatch time
- [x] Load-aware dispatch — least-connections over live servers
- [x] **Partition tolerance** — autonomous gameplay + durable on-disk outbox
- [x] **Eventual consistency** — additive deltas reconcile after heal
- [x] **Idempotency / exactly-once effect** — `round_id` ledger, transactional
- [x] **Mutual exclusion across the cluster** — one seat per account, leased by heartbeat
- [x] **Partition *handling*** — holder-side lease expiry: the game server freezes new
      rounds before central may reassign its players (`LEASE_TIMEOUT < SEAT_TAKEOVER_TTL`)
- [x] Authentication across trust boundaries — signed, expiring, server-bound tokens

See [09 — Partition-Tolerance Demo](09-partition-demo.md) for the script that
exercises all of this in one sitting.
