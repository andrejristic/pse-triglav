"""SHARED_LIB's log: append-only and hash-chained.

Every entry carries the hash of the one before it, so a changed, removed or
reordered entry breaks the chain. Nothing here reads a clock: entries are
numbered by step, so the same run always gives the same log.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

GENESIS = "0" * 64


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def entry_hash(prev: str, step: int, kind: str, data: dict) -> str:
    return hashlib.sha256(f"{prev}|{step}|{kind}|{canonical(data)}".encode()).hexdigest()


@dataclass
class Chain:
    entries: list[dict] = field(default_factory=list)

    @property
    def head(self) -> str:
        return self.entries[-1]["hash"] if self.entries else GENESIS

    def append(self, step: int, kind: str, data: dict) -> str:
        h = entry_hash(self.head, step, kind, data)
        self.entries.append({"step": step, "kind": kind, "data": data, "prev": self.head, "hash": h})
        return h

    def verify(self) -> tuple[bool, str]:
        prev = GENESIS
        for i, e in enumerate(self.entries):
            if e["prev"] != prev:
                return False, f"entry {i}: does not follow the one before it"
            if entry_hash(prev, e["step"], e["kind"], e["data"]) != e["hash"]:
                return False, f"entry {i}: its content was changed"
            prev = e["hash"]
        return True, "ok"
