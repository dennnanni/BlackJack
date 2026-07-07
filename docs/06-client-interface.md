# 06 — Main Server: `client_interface`

**Path:** `main_server/client_interface/`
**Package:** `client`
**Run with:** `poetry run client`
**Port:** `5000` (exposed as `16000` in Docker)
**Role:** The **player-facing web application**. It serves the HTML pages, handles
registration/login (with Flask-Login sessions), shows the player's balance, and — when the
player clicks "Play" — picks a game server, mints a JWT, and redirects the browser there.

It owns **no database**; it calls `database_interface` over HTTP for everything.

## File map

```
client_interface/
└── client/
    ├── __init__.py        # create_app(): Flask-Login, SocketIO, Fernet(SHARED_SECRET), DATABASE_URL
    ├── main.py            # entry point: socketio.run(app, port=5000)
    ├── constants.py       # endpoint paths + INITIAL_BALANCE = 1000
    ├── routes.py          # registers the web blueprint
    ├── event_handlers.py  # wires Socket.IO events → controller functions
    ├── controller/
    │   ├── web_controller.py      # HTTP routes (pages + login/register/logout POST)
    │   ├── routes_controller.py   # login_user() / register_user() business logic
    │   ├── client_controller.py   # Socket.IO handlers: get_user_info / get_game_server
    │   └── dispatcher.py          # load-balancer: pick a game server
    ├── model/
    │   └── structures.py          # UserSession (Flask-Login user)
    ├── utils/
    │   └── security.py            # password hashing + JWT minting
    └── templates/
        ├── access.html            # login/register page
        └── home.html              # logged-in home: balance + "Play"
```

## Bootstrapping (`__init__.py`)

On import this module:
- Loads `.env` and reads **`SHARED_SECRET`** → builds a `Fernet` instance
  (`fernet_shared_secret`). Used to decrypt a game server's stored key when minting a JWT.
- Reads **`DATABASE_URL`** (default `http://localhost:5001`).
- Creates a `SocketIO` with `manage_session=False` (Flask-Login owns the session).

`create_app()` wires up:
- The web Blueprint (pages + auth POSTs).
- Socket.IO event handlers.
- **Flask-Login**: `login_view='client_interface.login'`; an `unauthorized_handler` that
  redirects to `/login`; and a `user_loader` that rebuilds a `UserSession(username)` from the
  session cookie.

## The two layers: HTTP routes vs. Socket.IO events

This service uses **both** transports, for different jobs:

- **HTTP (form posts / page loads)** → account lifecycle (register, login, logout) and page rendering.
- **Socket.IO (with acknowledgement callbacks)** → dynamic data the logged-in page needs:
  fetching the balance, and requesting a table to join.

### HTTP routes — `web_controller.py`

| Method & path | Auth | What it does |
|---|---|---|
| `GET /` and `GET /login` | — | If already logged in, redirect to `/user/<username>`; else render `access.html` (login tab). |
| `GET /register` | — | Render `access.html` (register tab). |
| `GET /user/<username>` | `@login_required` | Render `home.html`. |
| `POST /login` | — | `login_user(...)`; redirect to home on success, re-render with error otherwise. |
| `POST /register` | — | `register_user(...)`; redirect to `/login` on success. |
| `POST /logout` | `@login_required` | `session.clear()`, redirect to `/login`. |

### Auth business logic — `routes_controller.py`

**`register_user(username, password)`**
1. `generate_hashed_password(password)` → produces `(hashed_password, salt)` (PBKDF2, see doc 09).
2. Build a `UserDatabase` with `balance = INITIAL_BALANCE (1000)`.
3. `POST /users/register` to `database_interface`.
4. On success, redirect to `/login`.

**`login_user(username, password)`**
1. `GET /users/salt?username=` → fetch the stored salt.
2. `get_hashed_password(password, salt)` → recompute the hash client-side.
3. `POST /users/login` with the hash.
4. On success, build a `UserSession` and call Flask-Login's `login_user(...)`; redirect to
   `/user/<username>`.

> The plaintext password is **only** ever present inside `client_interface` long enough to be
> hashed; only the hash is sent to `database_interface`. (There is a debug `print` of the
> plaintext password in `login_user` — remove that; see doc 12.)

### Socket.IO events — `client_controller.py`

Registered in `event_handlers.py`:

| Event (browser → server) | Handler | Purpose |
|---|---|---|
| `get_user_info` | `get_user_info(data)` | `GET /users/info` → returns `{data:{username, balance}}` to populate the home page. |
| `get_game_server` | `get_game_server(data)` | The "Play" button. Decides which game server to send the player to and returns a redirect + JWT. |

**`get_game_server` step by step:**
1. Look up the user's info; **refuse to play if balance ≤ 0**.
2. Check `/users/playing` (intended to prevent double-joining).
3. Ask the **`Dispatcher`** to pick a game server.
4. Mint a **JWT** (`create_token`) signed with that server's key.
5. Return `{redirect: "http://<server>/join", token: <jwt>}`.

The browser (`home.html`) receives this and does a hidden-form **POST** to the game server's
`/join` carrying the token (`postRedirect(...)`).

### The load balancer — `dispatcher.py`

```python
class Dispatcher:
    def pick_game_server(self):
        # GET /servers/load  → list of ServerLoad
        # pick the server with the fewest connected_users
        return min(servers_list, key=lambda s: s.connected_users)
```

Strategy = **least connections**. Returns `(server, None)` or `(None, error_message)` for
"no servers available". (Because nothing populates `userserver` yet, every server currently
reports 0 connections — so in practice it just picks the first one. See doc 12.)

## Security helpers — `utils/security.py`

Covered fully in [doc 09](09-security.md), but in brief:
- `generate_hashed_password(password)` → new random 16-byte salt + PBKDF2 hash.
- `get_hashed_password(password, salt)` → recompute hash for login.
- `create_token(username, server)` → decrypt the server's key with `SHARED_SECRET`, then
  `jwt.encode({username, iat, exp(+120s), server_id, server_ip, server_port}, key, HS256)`.

## The `UserSession` model — `model/structures.py`

A tiny Flask-Login user: a dataclass extending `BaseUser` + `UserMixin`, whose `get_id()`
returns the username. This is what `login_user()` stores and `user_loader` rebuilds.

## Templates

- **`access.html`** — Bootstrap login/register tabs; posts to `/login` and `/register`;
  shows a server-provided `error` banner.
- **`home.html`** — greets the user, fetches and shows balance via the `get_user_info` socket
  event, and on "Play" emits `get_game_server`, then POST-redirects to the returned game
  server with the JWT. Also has a logout button (`fetch POST /logout`).

Next: [07 — servers_interface](07-servers-interface.md).
