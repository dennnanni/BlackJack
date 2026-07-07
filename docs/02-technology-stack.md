# 02 — Technology Stack

Everything here comes from `pyproject.toml`, `docker-compose.yml`, and the import statements
in the code. Nothing is invented.

## Language & runtime

- **Python ≥ 3.11** (`pyproject.toml` → `python = ">=3.11"`).

## Dependency & packaging tool: Poetry

The project uses **[Poetry](https://python-poetry.org/)** (`poetry-core >= 2.0.0`) for
dependency management and packaging, **not** `pip`/`requirements.txt`.

`pyproject.toml` declares the project as a set of packages and, crucially, defines **four
console entry points** under `[tool.poetry.scripts]`:

```toml
[tool.poetry.scripts]
database    = "database_interface.database.main:main"   # → poetry run database
client      = "client_interface.client.main:main"       # → poetry run client
servers     = "servers_interface.servers.main:main"     # → poetry run servers
game_server = "game_server.src.main:main"                # → poetry run game_server
```

So you launch each service with `poetry run <name>`. These same commands are what
`docker-compose.yml` runs in each container.

The `packages = [...]` block tells Poetry where each importable package physically lives —
e.g. `database_interface` is found under `main_server/`, while `src` (the game server) is
found under `game_server/`. This is why imports such as `from common.structures import ...`
and `from src.model... import ...` resolve.

## Web framework: Flask + Flask-SocketIO

- **Flask** (`>=3.1.0`) — every service is a Flask app created by a `create_app()` factory.
  Routes are organized with **Blueprints**.
- **Flask-SocketIO** (`>=5.5.1`) — adds **WebSocket / Socket.IO** support on top of Flask.
  Used for real-time, bidirectional events:
  - `client_interface` uses it for `get_user_info` / `get_game_server` (browser → server callbacks).
  - `game_server` uses it heavily for the live game (`join`, `bet`, `player_action`, plus
    server-pushed events like `initial_cards`, `round_results`, …).
  Each app instantiates `SocketIO(cors_allowed_origins="*")` and runs via `socketio.run(app, ...)`.

> Note: services are started with `allow_unsafe_werkzeug=True` and `debug=True` (except the
> game server, which uses `debug=False`). That's the Werkzeug dev server — fine for
> development, not for production.

## Database: PostgreSQL + SQLAlchemy + psycopg2

- **PostgreSQL 17** — the database, run as the `postgres` service in Docker Compose.
- **SQLAlchemy** (`>=2.0.40`) — the ORM. Models live in
  `main_server/database_interface/database/orm/orm.py`. Only `database_interface` uses it.
- **psycopg2** (`>=2.9.10`) — the PostgreSQL driver SQLAlchemy talks through.

See [doc 04](04-data-model.md) for the schema.

## Authentication & crypto

- **Flask-Login** (`^0.6.3`) — session-based login for the **player** web app
  (`client_interface`). Provides `current_user`, `@login_required`, the `UserSession` model, etc.
- **cryptography** (`^45.0.2`) — specifically **Fernet** symmetric encryption. Two distinct uses:
  1. A global **`SHARED_SECRET`** (a Fernet key) used to secure the game-server↔central
     registration handshake.
  2. Each game server generates its **own** Fernet key at startup, used to sign/verify JWTs.
- **PyJWT** (`^2.10.1`) — **JWT** tokens. Used to authorize a player joining a specific game
  server, and to carry round results from a game server back to central.
- Python stdlib **`hashlib`** (PBKDF2-HMAC-SHA256) + **`secrets`** — password hashing with a
  per-user salt (in `client_interface/.../utils/security.py`).

All of this is explained in detail in [doc 09 — Security](09-security.md).

## HTTP client

- **requests** (`^2.32.3`) — used for **service-to-service** HTTP calls (wrapped by
  `common/http_requests.py` and by the game server's `central_api.py`).

## Configuration

- **python-dotenv** (`^1.1.0`) — loads environment variables from a `.env` file at the repo
  root. The most important variable is `SHARED_SECRET`. Others (`DATABASE_URL`,
  `SERVER_PORT`, `CENTRAL_SERVER_URL`, …) are read with `os.getenv`.

## Testing

- **pytest** (`^8.3.5`, dev dependency). Tests exist for:
  - the game logic (`game_server/tests/` — the most thorough suite),
  - the shared structures (`main_server/common/test/`),
  - HTTP integration against a running `servers_interface` (`main_server/servers_interface/test/`),
  - a (stale) DB test (`main_server/database_interface/test/`).
- `.vscode/settings.json` configures the VS Code test runner to use pytest, pointed at
  `game_server`.

## Containerization

- **Docker** + **Docker Compose**. `Dockerfile-poetry` builds a base image named `ppython`
  (Python + Poetry). `Dockerfile` builds on `ppython`, copies the repo, and runs
  `poetry install`. `docker-compose.yml` wires up Postgres + the three central services +
  one game server. `startup.sh` is the convenience entry point.

See [doc 11](11-running-locally.md) for how to actually run it.

## Front-end

There is **no JS build system / SPA framework**. The UI is plain server-rendered HTML
(Jinja2 templates) using **Bootstrap 5** (via CDN) for styling and the **Socket.IO client**
(via CDN) for real-time communication. Templates:

- `client_interface/.../templates/access.html` — login/register page.
- `client_interface/.../templates/home.html` — logged-in home (balance + "Play").
- `game_server/src/templates/index.html` — game table UI (**currently a stub**; the real
  UI is present but commented out — see [doc 12](12-known-issues.md)).

Next: [03 — The Common Module](03-common-module.md).
