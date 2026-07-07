# 12 — Known Issues & Rough Edges

This is an **honest inventory** of bugs, dead code, inconsistencies, and unfinished seams that
exist in the code *right now*. None of it is invented — every item points at a specific
location. As a new contributor, this is your map of "things that look done but aren't," and a
ready-made list of good first issues.

The project is clearly a **work in progress** (active `develop` branch, recent commits like
"fix test", "fixed jwt validation"). Expect rough edges.

---

## 🔴 Functional gaps (things that don't work end-to-end yet)

### 1. Game server → central result reporting is mismatched
- `game_server/src/central_api.py::send_results` posts `{"data": <fernet-encrypted blob>}` and
  sets **no** `X-Server-ID` header.
- `servers_interface` `POST /results` expects `{"token": <JWT>}` **plus** an `X-Server-ID`
  header (see `servers_controller.publish_results_route`).
- **Result:** balances are computed in-memory at the end of a round but never persisted.
- **Fix direction:** make `send_results` mint a JWT signed with the server's key (carrying
  `{"results":[...]}`) and send `X-Server-ID: <server_id>`, mirroring
  `servers_interface/test/test_http.py::test_publish_results`.

### 2. `update_user_list` targets a non-existent endpoint
- `central_api.update_user_list` POSTs to `servers_interface` `/users`, but **no `/users`
  route exists** there.
- **Result:** the call always fails; the `userserver` table is never populated this way.

### 3. Nothing populates the `userserver` join table
- `userserver` powers `connected_users` (load balancing) and `is_user_playing`. But no code
  path inserts/deletes rows in it.
- **Result:** `connected_users` is always 0 (so the dispatcher effectively picks the first
  server), and `/users/playing` always returns `false`.

### 4. The real game UI is commented out
- `game_server/src/templates/index.html` renders only a stub `<label>`. The full Socket.IO
  game client (join form, cards, bet/hit/stand/double, event handlers) exists but is inside an
  HTML comment.
- **Result:** after `POST /join` succeeds, there's no shipped UI that opens the Socket.IO
  connection and emits `join`. The game loop/events are reachable, but not from the bundled page.
- Note: that commented UI also references result fields (`res.outcome`, `res.payout`) that the
  server doesn't emit — it emits `username` and `balance_difference`. So the UI would need
  reconciling with the actual `round_results` payload.

---

## 🟠 Bugs in code that *is* on the happy path

### 5. `Result.to_dict()` in the game server returns `None`
- `game_server/src/model/game_structures.py`: `to_dict` calls `asdict(self)` but **doesn't
  return it**.
- Currently masked because `game_loop.py` serializes results with `vars(r)` and
  `send_results` is already broken (#1). Will bite whoever fixes #1 using `to_dict`.

### 6. Login of a non-existent user 500s instead of 4xx
- `database_interface` `login_user_route` has `# TODO check if user is in db`. If the username
  doesn't exist, `get_user` returns `None` and `user_db.password` raises `AttributeError`.

### 7. `Table.all_players_have_bet` compares a dict to a list
- `game_structures.py`: `return self.__game.get_bet() == self.__users` compares a
  `dict[User,float]` to a `list[User]` — never true. (The actual "all bet" check used by the
  loop is `Game.all_players_have_bet`/`place_bet`'s length comparison, so this `Table` method
  appears unused, but it's a latent trap.)

---

## 🟡 Stale tests

### 8. `test_database_actions.py` asserts an obsolete return value
- Asserts `add_user(...) == 'User added successfully'`, but `add_user` now returns `True`.
  This test **fails** if run.

### 9. `test_http.py` quirks
- `test_registration` has an early `return` before the `RegisteredServer` assertions (so the
  later asserts are dead), and `test_publish_results` posts to `/result` (singular) while the
  route is `/results`. It's a manual harness, not CI-grade.

---

## ⚪ Minor / cosmetic

- **Stray import:** `common/structures.py` line 2 has `from turtle import st` (unused).
- **Debug prints of sensitive data:** `client_interface.routes_controller.login_user` prints
  the plaintext username **and password**.
- **`max_users` is hard-coded** to `10` in the DB query (`get_servers_with_user_count`), not
  stored per server. `MAX_USER_IN_TABLE` (3) and `MAX_NUMBER_OF_TABLE` (3) in the game server
  are separate, unrelated constants — and `MAX_NUMBER_OF_TABLE` isn't actually enforced.
- **Comment/behavior drift:** `game_loop.py` comment says players get "15 seconds" to act, but
  the code waits 60s (and 35s for bets).
- **Single-ace hand value:** `Hand.get_hand_value` only subtracts 10 once, so a hand with
  multiple aces over 21 isn't fully optimized (rare in practice, but not strictly correct).
- **Dev-grade config everywhere:** `SECRET_KEY='secret!'`, `debug=True`,
  `allow_unsafe_werkzeug=True`, `cors_allowed_origins="*"`, `postgres/postgres`. Fine for dev,
  not for production (see [doc 09](09-security.md)).
- **In-memory game state:** `user_map`, `table_game_map`, `table_manager` live in the game
  server process. Restart = all live tables lost. There's also no removal of users from
  `user_map`/tables on disconnect, so memory grows and stale users linger.
- **Disconnect handling:** there's no Socket.IO `disconnect` handler in the game server, so a
  player leaving mid-round isn't cleaned up.

---

## How to use this list

If you're looking for a **first contribution**, good self-contained candidates:
- Fix #5 (one-line `return`), #1 + #8 together (align result reporting + its test), or #6
  (guard the login lookup).
- Re-enable and reconcile the game UI (#4) — bigger, but the most visible win.

Cross-reference each item with the relevant deep-dive doc before changing code. And see
[doc 13](13-getting-started.md) for how to wire a change through the system safely.
