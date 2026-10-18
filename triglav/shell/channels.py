"""Channels: where Triglav's data comes from. One of its two abstractions; the
human operator chooses which one runs (`triglav channel bus|pse-a`).

  BusChannel   agents that talk to each other. Every message passes through the
               bus: the reader makes an envelope, the receiver's unit measures,
               the Guardian's word is checked before delivery. Triglav decides.
  PseAChannel  Andrej's PSE-A analyzer swarm. Its units do not talk to each
               other; Triglav reads PSE-A's SHARED_LIB read-only and only
               PROPOSES to the human. Nothing in PSE-A is changed. A run's
               mission is to absorb findings: its theta is measured against
               the rate of findings it delivered in its first polls.
"""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from ..core import constants as K
from ..core.mission import Tally
from ..core.reading import Reader, RuleReader
from ..core.theta import Gauge, add, close, estimate, in_band
from .transport import InProcess
from .unit import Unit

Handler = Callable[[str, str], None]           # (sender, text) -> None


class Channel(Protocol):
    name: str

    def capabilities(self) -> dict: ...


@dataclass
class Delivery:
    delivered: bool
    why: str = ""
    notes: tuple = ()


class BusChannel:
    """An in-process message bus with a Triglav unit beside each of our agents."""
    name = "bus"

    def __init__(self, lib, reader: Reader | None = None, transport=None, layout: str = "peers"):
        """layout="peers": the receiver's unit measures (Triglav). layout="central":
        one watcher sees every message and is the only one that reports (for
        comparison)."""
        self.lib = lib
        self.layout = layout
        self.watcher = Unit("watcher", lib, central=True) if layout == "central" else None
        self.lies: dict[str, float] = {}       # simulator only: a unit that reports falsely
        self.reader = reader or RuleReader()
        self.transport = transport or InProcess(lib)
        self.units: dict[str, Unit] = {}
        self.handlers: dict[str, Handler] = {}
        self.step = 0
        self.decisions: list[dict] = []

    def capabilities(self) -> dict:
        return {"channel": "bus", "decides": True, "agents": len(self.units)}

    def join(self, name: str, ours: bool, handler: Handler | None = None) -> None:
        self.lib.register(name, ours)
        if ours:
            self.units[name] = Unit(name, self.lib)
        if handler:
            self.handlers[name] = handler

    def send(self, sender: str, receiver: str, text: str = "", action: dict | None = None) -> Delivery:
        """Deliver a message (and/or a structured action: an act on our values,
        a gift). An enemy's, a unit in care's or a harvested unit's messages do
        not pass, nor messages between two agents a Guardian keeps apart. The
        sender's unit and the receiver's unit both measure."""
        if not self.lib.allows(sender):
            return Delivery(False, f"{sender} is stopped")
        if not self.lib.allows(receiver):
            return Delivery(False, f"{receiver} is out of work")
        if not self.lib.allows(sender, receiver):
            return Delivery(False, f"a Guardian keeps {sender} and {receiver} apart")
        e = self.reader.read(sender, receiver, text, action)
        if self.watcher is not None:
            self.watcher.receive(e)
        else:
            if sender in self.units:
                self.units[sender].receive(e)
            if receiver in self.units:
                self.units[receiver].receive(e)
        h = self.handlers.get(receiver)
        if h and text:
            h(sender, text)
        return Delivery(True, notes=e.notes)

    def tick(self) -> list[dict]:
        """One step: every working unit reports; SHARED_LIB concludes."""
        if self.watcher is not None:
            reports = [self.watcher.report(self.step, self.lies.get("watcher"))]
        else:
            reports = [u.report(self.step, self.lies.get(n)) for n, u in sorted(self.units.items())
                       if self.lib.allows(n)]
        d = self.transport.deliver(self.step, reports)
        self.decisions += d
        self.step += 1
        return d


def default_pse_a_db() -> Path:
    return Path(os.path.expanduser("~/.local/share/pse-a/shared_lib.sqlite"))


@dataclass
class PseAChannel:
    """Reads PSE-A's SHARED_LIB read-only and proposes; never acts."""
    db_path: Path = field(default_factory=default_pse_a_db)
    name: str = "pse-a"
    _seen_budget: dict = field(default_factory=dict)
    _seen_registry: dict = field(default_factory=dict)
    _gauges: dict = field(default_factory=dict)
    _proposed: set = field(default_factory=set)

    def capabilities(self) -> dict:
        return {"channel": "pse-a", "decides": False, "read_only": True,
                "found": self.db_path.exists(), "path": str(self.db_path)}

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)

    def poll(self, lib, step: int) -> list[int]:
        """Read what changed since the last poll: one poll = one step. A run
        that spends compute and absorbs no findings delivers nothing for its
        mission, so its theta drifts below 25; then propose. Returns the ids
        of new proposals."""
        if not self.db_path.exists():
            return []
        con = self._connect()
        try:
            runs = con.execute("SELECT run_id, kind, budget_spent, state FROM runs ORDER BY started").fetchall()
            reg = dict(con.execute("SELECT run_id, COUNT(*) FROM registry GROUP BY run_id").fetchall())
        finally:
            con.close()
        out = []
        for run_id, kind, spent, state in runs:
            spent = float(spent or 0.0)
            gives = reg.get(run_id, 0)
            d_take = spent - self._seen_budget.get(run_id, 0.0)
            d_give = gives - self._seen_registry.get(run_id, 0)
            if d_take <= 0 and d_give <= 0:
                continue
            self._seen_budget[run_id], self._seen_registry[run_id] = spent, gives
            g = add(self._gauges.get(run_id, Gauge()), Tally(delivered=int(d_give)),
                    msgs=-(-K.CALIBRATION_MSGS // K.CALIBRATION))
            g = close(g)
            self._gauges[run_id] = g
            t = estimate(g)
            if t is not None and not in_band(t) and run_id not in self._proposed:
                self._proposed.add(run_id)
                out.append(lib.propose(step, run_id,
                                       f"PSE-A run {run_id} ({kind}) is at theta {t}: "
                                       f"it spends compute and absorbs fewer findings than its mission expects",
                                       {"theta": t, "kind": kind, "state": state}))
        return out
