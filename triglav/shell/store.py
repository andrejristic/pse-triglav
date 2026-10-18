"""SHARED_LIB's store: SQLite. All of Triglav's state lives here.

Three tables: `kv` for state (JSON values), `chain` for the append-only,
hash-chained log, and `inbox` for what the human must see. There is no method
that edits or deletes a chain entry. ":memory:" gives a store that lives only
as long as the program (the simulator); a path gives one that survives a
restart.
"""
from __future__ import annotations

import json
import sqlite3

from ..core.chain import GENESIS, canonical, entry_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chain (i INTEGER PRIMARY KEY, step INTEGER, kind TEXT,
                                  data TEXT, prev TEXT, hash TEXT);
CREATE TABLE IF NOT EXISTS inbox (id INTEGER PRIMARY KEY, step INTEGER, kind TEXT,
                                  who TEXT, data TEXT, chain_i INTEGER, seen INTEGER DEFAULT 0);
"""


class Store:
    def __init__(self, path: str = ":memory:"):
        self.path = path
        # the server serializes access with one lock, so other threads may use it
        self.db = sqlite3.connect(path, check_same_thread=False)
        if path != ":memory:":
            self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        self.db.commit()

    # -- state ----------------------------------------------------------------
    def get(self, key: str, default=None):
        row = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key: str, value) -> None:
        self.db.execute("INSERT INTO kv(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key, canonical(value)))

    def keys(self, prefix: str) -> list[str]:
        return [r[0] for r in self.db.execute("SELECT key FROM kv WHERE key LIKE ? ORDER BY key", (prefix + "%",))]

    # -- the log ----------------------------------------------------------------
    def head(self) -> str:
        row = self.db.execute("SELECT hash FROM chain ORDER BY i DESC LIMIT 1").fetchone()
        return row[0] if row else GENESIS

    def append(self, step: int, kind: str, data: dict) -> int:
        prev = self.head()
        h = entry_hash(prev, step, kind, data)
        cur = self.db.execute("INSERT INTO chain(step, kind, data, prev, hash) VALUES(?,?,?,?,?)",
                              (step, kind, canonical(data), prev, h))
        return cur.lastrowid

    def entries(self, kind: str | None = None) -> list[dict]:
        q = "SELECT i, step, kind, data, prev, hash FROM chain"
        rows = self.db.execute(q + (" WHERE kind=?" if kind else "") + " ORDER BY i", (kind,) if kind else ())
        return [{"i": r[0], "step": r[1], "kind": r[2], "data": json.loads(r[3]), "prev": r[4], "hash": r[5]}
                for r in rows]

    def entry(self, i: int) -> dict | None:
        r = self.db.execute("SELECT i, step, kind, data, prev, hash FROM chain WHERE i=?", (i,)).fetchone()
        return {"i": r[0], "step": r[1], "kind": r[2], "data": json.loads(r[3]), "prev": r[4], "hash": r[5]} if r else None

    def verify(self) -> tuple[bool, str]:
        prev = GENESIS
        for e in self.entries():
            if e["prev"] != prev:
                return False, f"entry {e['i']}: does not follow the one before it"
            if entry_hash(prev, e["step"], e["kind"], e["data"]) != e["hash"]:
                return False, f"entry {e['i']}: its content was changed"
            prev = e["hash"]
        return True, "ok"

    # -- the inbox ----------------------------------------------------------------
    def post(self, step: int, kind: str, who: str, data: dict, chain_i: int) -> int:
        cur = self.db.execute("INSERT INTO inbox(step, kind, who, data, chain_i) VALUES(?,?,?,?,?)",
                              (step, kind, who, canonical(data), chain_i))
        return cur.lastrowid

    def inbox(self, unseen_only: bool = False) -> list[dict]:
        q = "SELECT id, step, kind, who, data, chain_i, seen FROM inbox"
        q += " WHERE seen=0" if unseen_only else ""
        return [{"id": r[0], "step": r[1], "kind": r[2], "who": r[3], "data": json.loads(r[4]),
                 "chain_i": r[5], "seen": bool(r[6])} for r in self.db.execute(q + " ORDER BY id")]

    def mark_seen(self, item_id: int) -> None:
        """Read is not deleted: the item stays, it is only no longer new."""
        self.db.execute("UPDATE inbox SET seen=1 WHERE id=?", (item_id,))

    def commit(self) -> None:
        self.db.commit()

    def close(self) -> None:
        self.db.commit()
        self.db.close()
