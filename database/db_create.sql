--DROP DATABASE IF EXISTS BlackJack;
--CREATE DATABASE BlackJack;
--\c BlackJack

CREATE TABLE "user" (
    username TEXT PRIMARY KEY,
    password TEXT NOT NULL,
    salt TEXT NOT NULL,
    balance NUMERIC(10, 2) DEFAULT 0.0
);

CREATE TABLE gameserver (
    id SERIAL PRIMARY KEY,
    ip TEXT NOT NULL,
    port INT NOT NULL,
    key TEXT NOT NULL
);

CREATE TABLE userserver (
    username TEXT REFERENCES "user"(username) ON DELETE CASCADE,
    idserver INT REFERENCES gameserver(id) ON DELETE CASCADE,
    PRIMARY KEY (username, idserver)
);
