# 09 — Security & Encryption

This project uses **three distinct cryptographic mechanisms** for three different problems.
New developers get confused because all three involve "keys" — so here they are, side by side,
with exactly what each protects.

| Mechanism | Library | Protects | Key material |
|---|---|---|---|
| **Password hashing** | `hashlib` (PBKDF2) + `secrets` | stored user passwords | per-user random salt |
| **Fernet symmetric encryption** | `cryptography.fernet` | game-server ↔ central registration handshake; storage of per-server keys | global `SHARED_SECRET` + each server's own key |
| **JWT** | `PyJWT` | authorizing a player to join a game server; carrying round results | a game server's own Fernet key (used as the HMAC secret) |

## 1. The shared secret

A single **Fernet key** named `SHARED_SECRET`, generated once by `secret_generator.py`:

```python
from cryptography.fernet import Fernet
secret = Fernet.generate_key()
# written to .env as  SHARED_SECRET=<key>
```

Every component that participates in the registration handshake loads it from `.env`:
`client_interface`, `servers_interface`, and each `game_server`. It is the root of trust that
lets these processes prove to each other they're part of the same system.

> In Docker, `SHARED_SECRET` must be present in the environment / `.env` for the services that
> require it; `client_interface`, `servers_interface`, and `game_server` all raise on startup
> if it's missing.

## 2. Password hashing (`client_interface/utils/security.py`)

Passwords are **never** stored or transmitted in plaintext past `client_interface`.

```python
def get_hashed_password(password, salt):
    salt_bytes = base64.b64decode(salt)
    hash_bytes = hashlib.pbkdf2_hmac('sha256', password.encode(), salt_bytes, 100_000)
    return base64.b64encode(hash_bytes).decode()

def generate_hashed_password(password):
    salt = secrets.token_bytes(16)            # 128-bit random salt
    salt_b64 = base64.b64encode(salt).decode()
    return get_hashed_password(password, salt), salt_b64
```

- **Algorithm:** PBKDF2-HMAC-SHA256, **100 000 iterations**, 16-byte salt.
- **Registration:** generate salt + hash → store both in the `user` table (via `database_interface`).
- **Login:** fetch the stored salt (`GET /users/salt`), recompute the hash from the submitted
  password, send the *hash* to `POST /users/login`, which just string-compares it to the stored
  hash. The DB service therefore never sees plaintext, and the salt makes precomputed-table
  attacks impractical.

## 3. The registration handshake (Fernet)

When a `game_server` boots, it must register with `servers_interface` and establish a
per-server key that central can later use to verify its tokens. Step by step:

```
GAME SERVER                                    SERVERS_INTERFACE (central)             DATABASE
-----------                                    ---------------------------             --------
key = Fernet.generate_key()   # server's own identity key
payload = {ip, port, key}
enc = Fernet(SHARED_SECRET).encrypt(payload)
POST /register {encrypted: enc}  ───────────▶  decrypt enc with SHARED_SECRET → {ip,port,key}
                                               stored_key = Fernet(SHARED_SECRET)
                                                              .encrypt(key)   # never store raw
                                               POST /servers/register
                                                 {ip, port, key: stored_key}  ───────▶ INSERT gameserver
                                                                              ◀─────── server_id
                                               resp = {ip,port,key,server_id}
                                               enc2 = Fernet(key).encrypt(resp) # with SERVER's key
                                  ◀──────────  201 {encrypted: enc2}
decrypt enc2 with own key → learn server_id
```

Two clever properties:
- The DB stores the server's key **encrypted under the shared secret**
  (`Fernet(SHARED_SECRET).encrypt(server_key)`), so a DB leak alone doesn't expose signing keys.
- The response is encrypted under the **server's own key**, which only a holder of the shared
  secret could have produced correctly — so the game server can *trust* the `server_id` it gets back.

Relevant code: `game_server/src/central_api.py` (`register_game_server`),
`game_server/src/encryption.py`, and `servers_interface/.../servers_controller.py` (`index`).

## 4. Joining a game server (JWT)

When a logged-in player clicks "Play", `client_interface` must hand the browser a token that
the chosen game server will accept. It does this **without ever contacting the game server** —
purely by cryptographic trust:

```python
# client_interface/utils/security.py
def create_token(username, server):
    # server.key came from GET /servers/load and is Fernet(SHARED_SECRET).encrypt(server_key)
    private_key = fernet_shared_secret.decrypt(server.key.encode()).decode()  # = the server's real key
    token = {
        'username': username,
        'iat': now, 'exp': now + 120,        # valid 2 minutes
        'server_id': server.id, 'server_ip': server.ip, 'server_port': server.port,
    }
    return jwt.encode(token, private_key.encode(), algorithm='HS256')
```

The game server verifies it with the **same key** (its own module-level `key`):

```python
# game_server/src/controller/connection_controller.py
payload = jwt.decode(token, key, algorithms=['HS256'])
```

Why these two keys match: at registration the game server sent its `key` to central, which
stored `Fernet(SHARED_SECRET).encrypt(key)`. `client_interface` reads that encrypted value and
decrypts it with the shared secret to recover the exact same `key`, then signs the JWT with it.
So `jwt.decode(token, key)` succeeds **iff** the token was minted by a trusted
`client_interface`. The 2-minute expiry limits replay. (This is the "fixed jwt validation"
work in the git history.)

## 5. Reporting results (JWT, central side)

`servers_interface` `POST /results` expects a **JWT** signed with the reporting server's key:
1. Read `X-Server-ID` header.
2. `GET /servers/key?id=` → encrypted key, decrypt with shared secret.
3. `jwt.decode(token, that_key, HS256)`; the payload's `results` list is forwarded to
   `database_interface` to update balances.

This proves the results came from the genuine game server identified by `X-Server-ID`.

> ⚠️ As noted in docs 07/08/12, the game server's `send_results` currently posts a
> **Fernet-encrypted blob** (`{"data": ...}`) rather than a JWT and omits `X-Server-ID`, so it
> doesn't match this endpoint yet. The *verification design* above is sound; the *client side*
> needs to be aligned to it.

## Security caveats for production (observed, not invented)

These are dev-grade choices visible in the code — flagging them so you don't mistake them for
production-ready:
- Flask `SECRET_KEY` is the literal `'secret!'` in every `create_app()`.
- Services run on the Werkzeug dev server with `allow_unsafe_werkzeug=True` and `debug=True`.
- `cors_allowed_origins="*"` on all Socket.IO instances.
- Postgres credentials are `postgres/postgres` in `docker-compose.yml`.
- A few debug `print`s log sensitive-ish data (e.g. the plaintext password in
  `client_interface`'s `login_user`).

Next: [10 — End-to-End Flows](10-flows.md).
