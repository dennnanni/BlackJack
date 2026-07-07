# 07 — Main Server: `servers_interface`

**Path:** `main_server/servers_interface/`
**Package:** `servers`
**Run with:** `poetry run servers`
**Port:** `5002` (exposed as `16001` in Docker)
**Role:** The **API that game servers talk to**. Two jobs: (1) let a game server **register
itself** into the system, and (2) accept **round results** from a game server and forward them
to the database. From a game server's point of view, this is "the central server"
(`CENTRAL_SERVER_URL`).

It owns no database; it calls `database_interface` for persistence.

## File map

```
servers_interface/
└── servers/
    ├── __init__.py        # create_app(): Fernet(SHARED_SECRET), DATABASE_URL, SocketIO
    ├── main.py            # entry point: socketio.run(app, port=5002)
    ├── constants.py       # the database_interface endpoint paths it calls
    ├── routes.py          # registers the blueprint
    ├── event_handlers.py  # empty (no socket events)
    └── controller/
        └── servers_controller.py   # POST /register and POST /results
```

## Bootstrapping (`__init__.py`)

- Loads `.env`, reads **`SHARED_SECRET`**, builds `fernet_shared_secret`.
- Reads **`DATABASE_URL`**.
- Standard `create_app()` + a (no-op) SocketIO setup.

## Endpoints — `servers_controller.py`

### `POST /register` — game server registration

This is the heart of the **registration handshake**. Walk through it carefully, because it's
the trickiest crypto dance in the project (full picture in [doc 09](09-security.md)):

Input: `{ "encrypted": "<base64>" }` where the ciphertext was produced by the game server
encrypting `{ip, port, key}` with the **shared secret**.

1. Decrypt `encrypted` with `fernet_shared_secret` → cleartext JSON.
2. Parse it into a `Server(ip, port, key)`. Here `key` is the game server's **own freshly
   generated Fernet key** (in plaintext, but the whole message was protected by the shared secret).
3. Build `fernet_private = Fernet(server.key)` — i.e. an encryptor using the server's own key.
4. **Re-encrypt** the server's key with the shared secret and store *that* as
   `server.key` → this is what lands in the `gameserver.key` column. So the DB never holds the
   raw per-server key in cleartext; it holds `Fernet(SHARED_SECRET).encrypt(server_key)`.
5. `POST /servers/register` to `database_interface` → get back the new `server_id`.
6. Build a response payload = the original `{ip, port, key}` **plus** `server_id`, encrypt it
   with `fernet_private` (the server's own key), and return `{encrypted: ...}` with `201`.

Why encrypt the response with the server's key? So the game server can **decrypt it and trust
it** — only something that knows the shared secret could have produced a message correctly
encrypted under the key the game server just generated. It's mutual proof-of-secret.

### `POST /results` — accept round results

Input:
- Header **`X-Server-ID`**: the reporting game server's id.
- Body `{ "token": "<jwt>" }`: a JWT whose payload contains `{"results": [Result, ...]}`.

Steps:
1. Read and validate `X-Server-ID` (must be digits) — else `401`.
2. `GET /servers/key?id=<id>` from `database_interface` → the **encrypted** stored key.
3. Decrypt it with `fernet_shared_secret` → the game server's real signing key.
4. `jwt.decode(token, secret, algorithms=["HS256"])` — verifies the token was signed by that
   server. Handles `ExpiredSignatureError` / `InvalidTokenError` → `401`.
5. `POST /servers/results` to `database_interface` with `payload["results"]` → balances updated.
6. Return `200 {success:true}`.

This is the recently fixed JWT path (`git log`: "fixed jwt validation"). It mirrors how the
test in `test/test_http.py` builds a JWT and posts it with an `X-Server-ID` header.

> ⚠️ **Important mismatch to know about:** the game server's client code
> (`game_server/src/central_api.py::send_results`) does **not** currently send a JWT. It sends
> `{"data": <fernet-encrypted-blob>}` with **no `X-Server-ID` header**. That does not match
> what this `/results` endpoint expects (`{"token": <jwt>}` + header). So result reporting from
> a real game server is currently broken/inconsistent — only the test exercises the working
> path. See [doc 12](12-known-issues.md). This is a prime "good first fix".

## Constants — `constants.py`

The `database_interface` endpoints this service calls:
```python
REGISTER_NEW_SERVER_API_ENDPOINT = '/servers/register'
PUBLISH_RESULT_API_ENDPOINT      = '/servers/results'
GET_SERVER_KEY_API_ENDPOINT      = '/servers/key'
```

## Tests — `test/`

- `test_http.py` — **integration** tests that require a running `servers_interface`. It needs
  `SHARED_SECRET` and `TEST_KEY` env vars. `test_registration` encrypts a fake `Server` with
  the shared secret, POSTs to `/register`, and decrypts the response with `TEST_KEY`.
  `test_publish_results` builds a JWT and posts it to `/results`.
  (Note: there are minor URL/`return`-early quirks in this file; it's a manual harness more
  than a CI suite.)
- `key_gen.py` — a tiny utility that prints a fresh `Fernet.generate_key()`, handy for
  producing a `TEST_KEY`.

Next: [08 — The Game Server](08-game-server.md).
