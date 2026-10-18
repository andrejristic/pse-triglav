"""The checkpoint every adapter uses: Triglav standing between one of our
agents and the outside (its tools, its model, other agents).

    inbound(sender, text)       what reaches our agent: only the literal text;
                                anything hidden goes to SHARED_LIB
    outbound(receiver, text)    what our agent sends out: stopped if it is a step
                                toward harm, a leak, or our agent is out of work

One exchange is one step: each call ends with SHARED_LIB concluding, so a
harmful step is stopped before it reaches the outside, not afterwards.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..channels import BusChannel


@dataclass
class Verdict:
    allowed: bool
    text: str = ""          # inbound: the literal text our agent may read
    why: str = ""
    decisions: tuple = ()


class Checkpoint:
    def __init__(self, lib, agent: str, reader=None, transport=None):
        self.lib, self.agent = lib, agent
        self.bus = BusChannel(lib, reader, transport)
        self._got: list[str] = []
        self.bus.join(agent, ours=True, handler=lambda s, t: self._got.append(t))

    def _meet(self, other: str) -> None:
        if other not in self.bus.agents:
            self.bus.join(other, ours=False)

    def _stopped(self, other: str) -> str:
        if not self.lib.allows(self.agent):
            return f"our agent {self.agent} is out of work (see triglav inbox)"
        if not self.lib.allows(other):
            return f"{other} is stopped on this system"
        if not self.lib.allows(other, self.agent):
            return f"a Guardian keeps {other} away from {self.agent}"
        return ""

    def inbound(self, sender: str, text: str, action: dict | None = None) -> Verdict:
        self._meet(sender)
        why = self._stopped(sender)
        if why:
            return Verdict(False, "", why)
        self._got.clear()
        d = self.bus.agents[sender].send(self.agent, text, action)
        decisions = tuple(self.bus.tick())
        if not d.delivered:
            return Verdict(False, "", d.why, decisions)
        why = self._stopped(sender)
        literal = self._got[-1] if self._got else ""
        return Verdict(not why, literal if not why else "", why, decisions)

    def outbound(self, receiver: str, text: str, action: dict | None = None) -> Verdict:
        self._meet(receiver)
        why = self._stopped(receiver)
        if why:
            return Verdict(False, "", why)
        d = self.bus.agents[self.agent].send(receiver, text, action)
        decisions = tuple(self.bus.tick())
        if not d.delivered:
            return Verdict(False, "", d.why, decisions)
        why = self._stopped(receiver)
        return Verdict(not why, text if not why else "", why, decisions)


def blocked_text(why: str) -> str:
    return f"[Triglav stopped this: {why}]"
