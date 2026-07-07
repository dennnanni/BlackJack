# 05 — Main Server: `database_interface`

**Path:** `main_server/database_interface/`
**Package:** `database`
**Run with:** `poetry run database`
**Port:** `5001`
**Role:** The single gatekeeper of PostgreSQL. Exposes a small REST API; every other service
reads/writes data by calling it over HTTP (never by touching the DB directly).

## File map

```
database_interface/
└── database/
    ├── __init__.py        # create_app(), the SQLAlchemy engine/session, SocketIO instance
    ├── main.py            # entry point: socketio.run(app, port=5001)
    ├── routes.py          # registers the two blueprints
    ├── controller/
    │   ├── users_database_controller.py    # /users/* endpoints
    │   └── servers_database_controller.py  # /servers/* endpoints
    ├── model/
    │   └── database_actions.py             # all DB read/write functions (see doc 04)
    └── orm/
        └── orm.py                          # SQLAlchemy models (see doc 04)
```

## Bootstrapping (`__init__.py`)

- Builds the SQLAlchemy `engine` from `DATABASE_URL` (env), creating a `SessionLocal` factory.
- Instantiates a `SocketIO` object — but note the event-handler registration is
  **commented out**, so this service has no real-time behavior. Socket.IO is effectively
  unused here; it runs as a plain REST service. (`socketio.run` is just how all services in
  this project are started.)
- `create_app()` registers routes and returns the Flask app.

## Routes

Two Blueprints, mounted with URL prefixes in `routes.py`:

```python
app.register_blueprint(servers_routes_bp, url_prefix='/servers')
app.register_blueprint(users_routes_bp,  url_prefix='/users')
```

### `/users/*` — `users_database_controller.py`

| Method & path | Input | Behavior | Output |
|---|---|---|---|
| `POST /users/register` | `UserDatabase` JSON (`username, password, salt, balance`) | `add_user(...)` | `201` `{success:true}` / `400` |
| `GET /users/salt?username=` | username in query | `get_user(...).salt` | `200 {salt}` / `400` / `404` |
| `POST /users/login` | `UserLogin` JSON (`username, password`) | compares submitted hash to stored hash | `200 {success:true}` / `400` |
| `GET /users/info?username=` | username in query | `get_user(...)` → `UserInfo` | `200 {data: {username, balance}}` / `400` / `404` |
| `GET /users/playing?username=` | username in query | `is_user_playing(...)` | `200 {playing: bool}` / `400` |

How the **login check** works here: the caller (`client_interface`) has *already* hashed the
submitted password using the user's salt (fetched via `/users/salt`). This endpoint just does
a string comparison `user.password == user_db.password`. So plaintext passwords never reach
this service. (See [doc 09](09-security.md) and [doc 10](10-flows.md).)

> 🐞 `login_user_route` has a `# TODO check if user is in db` — if the username doesn't exist,
> `get_user` returns `None` and `user_db.password` raises an `AttributeError` (500), rather
> than a clean 400/404. Worth hardening.

### `/servers/*` — `servers_database_controller.py`

| Method & path | Input | Behavior | Output |
|---|---|---|---|
| `GET /servers/load` | — | `get_servers_with_user_count()` → list of `ServerLoad` | `200 {data: [ServerLoad...]}` / `500` |
| `POST /servers/register` | `GameServer` JSON (`ip, port, key`) | `register_server(...)` | `201 {server_id}` / `400` / `500` |
| `GET /servers/key?id=` | server id in query | `get_server_key(...)` | `200 {encrypted: key}` / `400` / `404` |
| `POST /servers/results` | list of `Result` dicts | `update_users_balance(...)` | `200 {success:true}` / `400` |

Notes:
- `/servers/load` is what the player dispatcher uses to pick the least-loaded server.
- The `key` returned by `/servers/key` is the game server's Fernet key **as stored**, i.e.
  still encrypted with the `SHARED_SECRET`. The field is literally named `encrypted`. The
  caller (`servers_interface`) decrypts it to verify JWTs. (See doc 09.)
- `/servers/results` is the DB-side terminus of the result-reporting chain: game server →
  `servers_interface` → here → balances updated.

## Who calls this service

- **`client_interface`** → `/users/register`, `/users/salt`, `/users/login`, `/users/info`,
  `/users/playing`, `/servers/load`.
- **`servers_interface`** → `/servers/register`, `/servers/key`, `/servers/results`.

It never calls anyone else; it's a leaf service sitting in front of Postgres.

## Tests

`main_server/database_interface/test/test_database_actions.py` asserts
`add_user(...) == 'User added successfully'`. **This test is stale** — `add_user` now returns
`True`, not that string. It will fail if run. (See [doc 12](12-known-issues.md).)

Next: [06 — client_interface](06-client-interface.md).
