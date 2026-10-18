"""The PSE unit that lives beside each of our agents.

It measures and reports; it never concludes. Two things are measured on every
incoming message:
  - our own agent's theta and who pushed it (OwnTheta);
  - the theta of the sender, as an assumption from its behaviour
    (BehaviourTheta) -- this is how units watch each other.
Once per step the unit sends one Report to SHARED_LIB.
"""
from __future__ import annotations

from .messages import Message, Report
from .theta import BehaviourTheta, OwnTheta


class Unit:
    def __init__(self, name: str, kinds: dict[str, str], baseline_ours: str = "class"):
        self.name = name
        self.baseline_ours = baseline_ours     # "class" (Triglav) or "own" (Perun's rule)
        self._kinds = kinds          # who -> "ours" | "colleague" | "stranger" (from SHARED_LIB)
        self.own = OwnTheta()
        self.peers = BehaviourTheta()
        self._seen: set[str] = set()
        self._harms: list[tuple[str, str, bool]] = []

    def receive(self, m: Message) -> None:
        kind = self._kinds.get(m.sender, "stranger")
        self.peers.observe(m.sender, kind, m.takes, m.gives,
                           baseline=self.baseline_ours if kind == "ours" else "own")
        self.own.read(m.sender, m.c, m.n)
        self._seen.add(m.sender)
        if m.harm:
            self._harms.append((m.sender, m.harm, m.mandate))

    def report(self, step: int, lie: float | None = None) -> Report:
        """`lie`, if given, replaces every peer theta this unit reports (the
        simulator uses it for a unit that reports falsely)."""
        peers = {}
        for who in sorted(self._seen):
            t = self.peers.theta(who)
            if t is not None:
                peers[who] = (lie if lie is not None else t, self.peers.n(who))
        r = Report(step=step, observer=self.name, observer_theta=self.own.theta, peers=peers,
                   pushed_by=self.own.take_peaks(), out_run=self.own.out_run,
                   harms=tuple(self._harms))
        self._seen.clear()
        self._harms.clear()
        return r
