# 13 — How to Start Contributing

You've read the architecture. Now: where does your code actually go? This doc gives you the
**mental checklist** and a few **worked recipes** for the kinds of changes you'll most likely
make.

## The golden rules of this codebase

1. **Only `database_interface` touches the database.** If your feature needs data, you add a
   route + a `database_actions` function there, and **call it over HTTP** from wherever you
   need it (using `common.http_requests`). Never `import sqlalchemy` outside
   `database_interface`.
2. **Shared shapes go in `common/structures.py`.** If two services exchange an object, model
   it as a dataclass there (and remember the game server keeps its own copies — keep them in
   sync; see [doc 03](03-common-module.md)).
3. **String keys go in `common/response_fields.py`.** Don't hard-code `'error'`/`'data'` etc.
4. **Each service is a Flask app made by `create_app()`** with Blueprint(s) registered in its
   `routes.py`. Follow the existing controller/model/(utils) folder split.
5. **Real-time = Socket.IO; request/response = HTTP.** Use whichever the surrounding code uses
   for that interaction (see [doc 06](06-client-interface.md) and [doc 08](08-game-server.md)).
6. **The three crypto mechanisms are distinct** (password hash / Fernet handshake / JWT). Reuse
   the existing helpers; don't invent a fourth. See [doc 09](09-security.md).

## "Where do I put it?" cheat sheet

| I want to… | Touch this |
|---|---|
| Add/inspect a DB column or query | `database_interface/.../orm/orm.py` + `model/database_actions.py` (+ `database/db_create.sql` for parity) |
| Expose new data over the DB API | a route in `database_interface/.../controller/*_database_controller.py` |
| Change a page the player sees | `client_interface/.../templates/*.html` + a route in `web_controller.py` |
| Change login/registration logic | `client_interface/.../controller/routes_controller.py` (+ `utils/security.py` for hashing) |
| Change how players get matched to servers | `client_interface/.../controller/dispatcher.py` |
| Change the JWT issued to players | `client_interface/.../utils/security.py::create_token` (+ verify in `game_server/.../connection_controller.py`) |
| Change the game-server registration handshake | `game_server/src/central_api.py` ↔ `servers_interface/.../servers_controller.py` |
| Change Blackjack rules / payouts | `game_server/src/model/game_structures.py` (and its tests in `game_server/tests/`) |
| Change round flow / timeouts / phases | `game_server/src/game_loop.py` |
| Add a real-time game action | `game_server/src/event_handlers.py` (+ the game UI) |

## Recipe 1 — Add a new field to the user-facing API

Say you want `/users/info` to also return when the account was created.

1. **Schema:** add a `created_at` column to `User` in `orm/orm.py` (and to `db_create.sql`).
2. **Data shape:** add the field to `UserInfo`/`UserDatabase` in `common/structures.py`
   (and mirror anywhere the game server reconstructs users, if relevant).
3. **DB API:** `get_user_info_route` already builds a `UserInfo` from the row — include the new
   field there.
4. **Consumer:** in `client_interface`, the `get_user_info` socket handler just forwards the
   `data` dict, so `home.html`'s `response.data.created_at` is now available — render it.

## Recipe 2 — Add a new game action (e.g. "split")

1. **Model:** add the logic to `Game`/`User`/`Hand` in `game_structures.py`. Write tests in
   `game_server/tests/` first — the model is well covered, keep it that way.
2. **Event:** handle `action == 'split'` in `event_handlers.handle_player_action`, emitting an
   appropriate Socket.IO event to the room.
3. **Loop:** make sure `Game.all_players_done()` still terminates correctly for the new state.
4. **UI:** add a button + a `socket.on(...)` handler in the game template (which first needs to
   be un-commented; see [doc 12](12-known-issues.md) #4).

## Recipe 3 — Persist round results (close the loop in [doc 10](10-flows.md) Flow F)

This is issue #1 in [doc 12](12-known-issues.md) and a high-value fix:

1. In `game_server/src/central_api.py::send_results`, build a JWT instead of a Fernet blob:
   `jwt.encode({"results":[r.to_dict() for r in results]}, self.new_key, algorithm="HS256")`
   — and first fix `Result.to_dict()` (issue #5) to actually `return asdict(self)`.
2. POST `{"token": jwt}` with header `X-Server-ID: str(self.server_id)` to `/results`.
3. Verify against `servers_interface/test/test_http.py::test_publish_results`, which already
   demonstrates the exact contract the central endpoint expects.
4. Confirm `database_interface.update_users_balance` then moves the balances.

## Workflow conventions

- **Branches:** work happens on `develop` (default branch shown by git). `master` is the main
  branch; there's also `feature/refactor` on the remote. Branch off `develop` for new work.
- **Tests:** run `poetry run pytest game_server` before/after model changes. Add tests for new
  model logic.
- **Run it:** use Docker Compose (`./startup.sh`) for a full-system smoke test, or bare
  `poetry run <service>` to iterate on one piece. See [doc 11](11-running-locally.md).
- **Don't forget the `.env`** with a `SHARED_SECRET` (`python secret_generator.py`).

## A reading order if you're implementing today

1. [doc 01](01-architecture.md) — the map.
2. The doc for the service you're changing (05–08).
3. [doc 10](10-flows.md) — to see your change in the context of a full journey.
4. [doc 12](12-known-issues.md) — so you don't trip over a known bug or build on dead code.

Welcome aboard. 🎲
