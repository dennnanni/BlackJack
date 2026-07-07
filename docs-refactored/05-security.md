# 05 — Security

The system uses exactly **two** cryptographic mechanisms (down from three schemes
before the refactor).

## 1. Password hashing (central only)

`central_server/auth.py`: **PBKDF2-HMAC-SHA256**, 100 000 iterations, a random
128-bit per-user salt, both stored base64 in the `user` table. Login re-derives the
hash from the attempt + stored salt and compares. Plaintext passwords are never
stored or logged.

## 2. One shared secret, two kinds of JWT

`secret_generator.py` writes a random `SHARED_SECRET` to `.env`. It is known only to
the central server and the game servers (injected via environment), never to
browsers. It is the HS256 signing key for:

### (a) Server tokens — "I am part of the system"

Attached by a game server (as `Authorization: Bearer …`) to every call to central.
Claims: `server_id` (absent only during the registration bootstrap, where knowing
the secret *is* the authorization), `iat`, `exp` (60 s). Central rejects missing,
forged and expired tokens, and requires the `server_id` claim on heartbeat/results.

### (b) Join tokens — "this player may enter that server"

Minted by central at dispatch, posted by the browser to the game server's `/join`.
Claims:

```json
{"sub": "<username>", "balance": 950.0, "server_id": 3, "iat": ..., "exp": "+120s"}
```

The game server verifies the signature and **checks `server_id` against its own id**,
so a token minted for one server is useless on every other. The username and balance
the game uses come **from this signed token** — the browser has no way to inject its
own balance (before the refactor, it literally sent one in the `join` event; that
hole is closed).

## Trust boundaries, summarized

| Principal | Trusts central with | Proves itself by |
|---|---|---|
| Browser / player | account, balance | Flask-Login session (password login) |
| Game server | registry, balance updates | Bearer JWT signed with `SHARED_SECRET` |
| Central | — (source of truth) | being the only address everyone is configured with |

## The documented trade-off (say this in the report)

With a *single* shared secret, any game server could technically verify or mint a
token meant for another. We accept this because: (1) the only holders of the secret
are our own processes — there is no third-party tenancy; (2) join tokens are bound
to one server by the `server_id` claim and die after 2 minutes; (3) results are
deduplicated by `round_id`, so even a replayed results-call cannot double-apply.
In exchange we deleted the entire Fernet handshake (double encryption at
registration, per-server keys stored encrypted in the DB, a key-lookup endpoint) —
the part of the old system where most of its complexity and several of its bugs
lived. Net: a strictly simpler system that closes a real vulnerability
(client-supplied balance) while accepting a theoretical one (server-to-server token
reuse inside our own trust domain).

## Remaining dev-grade defaults (fine for the course, not for production)

- Postgres credentials `postgres/postgres` in compose;
- HTTP everywhere (no TLS), cookies without `Secure`;
- Flask dev server (with `allow_unsafe_werkzeug` in the game server for Docker);
- `SECRET_KEY` random per boot: sessions do not survive a restart (pin it via the
  environment if that matters).

Next: [06 — Distributed-Systems Mechanisms](06-distributed-systems.md).
