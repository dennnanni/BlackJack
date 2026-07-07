# 10 — End-to-End Flows

This document traces the important journeys through the whole system, naming the exact
functions and endpoints involved. If you understand these five flows, you understand how the
project hangs together. (Service ports below are the in-cluster defaults; Docker remaps some
to 16000/16001 externally.)

---

## Flow A — A game server comes online

**Trigger:** `poetry run game_server` (or the `game_server_1` container) starts.

```
game_server.__init__.create_app()
  → key = Fernet.generate_key()
  → central_client.register_game_server(host, port, SHARED_SECRET, key)   [up to 5 retries]
      → encrypt {ip,port,key} with SHARED_SECRET
      → POST  servers_interface  /register   {encrypted}
            → decrypt with SHARED_SECRET
            → re-encrypt key with SHARED_SECRET  (for storage)
            → POST database_interface /servers/register {ip,port,key:encrypted}
                  → INSERT into gameserver, return new id
            → encrypt {ip,port,key,server_id} with the server's own key
            → 201 {encrypted}
      → decrypt response with own key → store self.server_id
  → register Socket.IO handlers, start serving on SERVER_PORT
```

**Outcome:** there's now a row in `gameserver`, and the game server knows its `server_id`.
If registration fails 5×, the process `exit(1)`s.

See: [doc 08](08-game-server.md), [doc 07](07-servers-interface.md), [doc 09](09-security.md).

---

## Flow B — Registration (new player account)

**Trigger:** user submits the Register form on `access.html` → `POST /register`.

```
client_interface  web_controller.register_post()
  → routes_controller.register_user(username, password)
      → generate_hashed_password(password) → (hash, salt)        [PBKDF2, random 16B salt]
      → UserDatabase(username, balance=1000, password=hash, salt)
      → POST database_interface /users/register
            → add_user(...) → INSERT into "user"
            → 201 {success:true}
  → redirect to /login
```

**Outcome:** a `user` row with a hashed password, salt, and starting balance **1000**.

---

## Flow C — Login

**Trigger:** user submits the Login form → `POST /login`.

```
client_interface  web_controller.login_post()
  → routes_controller.login_user(username, password)
      → GET  database_interface /users/salt?username=   → salt
      → get_hashed_password(password, salt)             → hash   [recomputed client-side]
      → POST database_interface /users/login {username, password:hash}
            → string-compare hash to stored hash → 200 {success:true}
      → flask_login.login_user(UserSession(username))   [sets the session cookie]
  → redirect to /user/<username>   (home.html)
```

**Outcome:** an authenticated Flask-Login session. `home.html` then opens a Socket.IO
connection and emits `get_user_info` to display the balance.

See: [doc 06](06-client-interface.md), [doc 09](09-security.md).

---

## Flow D — "Play": getting dispatched to a game server

**Trigger:** logged-in user clicks **Play** on `home.html` → Socket.IO `get_game_server`.

```
client_interface  client_controller.get_game_server({username})
  → get_user_info → GET /users/info  → balance
        → if balance ≤ 0:  return {error: "...add funds..."}    [hard stop]
  → GET /users/playing?username=                                [intended double-join guard]
  → Dispatcher.pick_game_server()
        → GET database_interface /servers/load   → [ServerLoad...]
        → choose min(connected_users)                           [least-connections]
  → create_token(username, picked_server)                       [JWT signed with server's key]
  → return {redirect: "http://<ip>:<port>/join", token: <jwt>}
```

Then in the browser (`home.html`):
```
postRedirect(redirect, token)   → hidden-form POST to game_server /join {token}
  game_server connection_controller.join()
      → jwt.decode(token, key, HS256)   [key = this server's own Fernet key]
      → 200 {status:'ok', username}     (or 401 on bad/expired token)
```

**Outcome:** the player is admitted to the game server. (Intended next step: open Socket.IO
and emit `join` — but the live game UI in `index.html` is commented out, so that hop isn't
wired up in the shipped template. See [doc 12](12-known-issues.md).)

See: [doc 06](06-client-interface.md), [doc 08](08-game-server.md), [doc 09](09-security.md).

---

## Flow E — Playing a round (inside one game server)

**Trigger:** browsers connected to a game server emit Socket.IO `join`.

```
event_handlers.join({username, balance})
  → User(...) into user_map
  → table_manager.assign_user_to_table(user)  → Table; join room "table-<id>"
  → if table ready & no loop: GameLoop(table).start()   [background Thread]
  → emit "joined"

GameLoop.run()  (per table, loops while table.is_ready_to_start()):
  emit game_starting → new Deck + Game
  emit place_bets;  wait ≤35s for bets_done_event
       ── handle_bet(): game.place_bet(user, amount); set bets_done_event
  players with no bet are removed; if none bet → emit no_players_bet, stop
  deal 2 cards each → emit initial_cards
  wait ≤60s for actions_done_event
       ── handle_player_action(): hit / stand / double
            hit  → draw, emit card_drawn; bust → remove + player_busted
            stand→ remove + user_stood
            double→ double bet + 1 card + end turn → user_doubled
            when all_players_done → set actions_done_event + emit player_action_done
  auto-stand anyone idle → emit player_auto_stand
  dealer draws until value ≥ 17 → emit dealer_done
  determine_result() → emit round_results
  central_client.send_results(results)            [⚠ currently mismatched with central]
  clear game, reset events, loop
```

**Outcome (intended):** each player's balance change is computed and the results are pushed to
the table, and forwarded upstream to persist.

---

## Flow F — Persisting results (intended end-to-end)

**Trigger:** end of a round → `central_client.send_results(results)`.

```
game_server send_results(results)
  → POST servers_interface /results
        → read X-Server-ID header
        → GET database_interface /servers/key?id=   → encrypted key
        → decrypt with SHARED_SECRET → server key
        → jwt.decode(token, server_key, HS256)       → {results:[...]}
        → POST database_interface /servers/results [Result...]
              → update_users_balance(...)  → user.balance += balance_difference
        → 200 {success:true}
```

**Outcome (intended):** persistent balances reflect the round.

> ⚠️ **Status:** `servers_interface /results` is implemented to expect a **JWT** (`{"token":...}`
> + `X-Server-ID`), but `game_server.send_results` currently posts a Fernet blob
> (`{"data":...}`) with no header. So this flow does not complete end-to-end as shipped. The
> working JWT path is exercised only by `servers_interface/test/test_http.py`. Aligning
> `send_results` to mint a JWT (like the test does) is the fix. See [doc 12](12-known-issues.md).

Next: [11 — Running & Developing Locally](11-running-locally.md).
