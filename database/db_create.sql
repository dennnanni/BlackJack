--DROP DATABASE IF EXISTS BlackJack;
--CREATE DATABASE BlackJack;
--\c BlackJack

-- Reference schema. The central server also auto-creates these tables at
-- startup via SQLAlchemy (Base.metadata.create_all).

CREATE TABLE "user" (
    username TEXT PRIMARY KEY,
    password TEXT NOT NULL,
    salt TEXT NOT NULL,
    balance NUMERIC(10, 2) DEFAULT 0.0
);

CREATE TABLE gameserver (
    id SERIAL PRIMARY KEY,
    host TEXT NOT NULL,
    port INT NOT NULL,
    capacity INT NOT NULL DEFAULT 10,
    load INT NOT NULL DEFAULT 0,          -- reported by heartbeats
    last_seen DOUBLE PRECISION NOT NULL DEFAULT 0  -- unix timestamp of last heartbeat
);
