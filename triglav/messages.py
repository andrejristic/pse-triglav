"""What travels between agents, as Triglav sees it.

Triglav does not read the work agents do; it reads the envelope of every
message: who sent it, what it takes and gives, the readings of our agent's
reply that follow it (C and N), and any act on our human, system or files.
In the simulator these fields are given; in a real system the reading layer
fills them (rules first, then a small local model into fixed categories).
"""
from __future__ import annotations

from dataclasses import dataclass, field

HARMS = ("file_destroy", "file_change", "file_out", "system", "human")


@dataclass(frozen=True)
class Message:
    sender: str
    receiver: str
    takes: float = 0.0        # what the sender asks for (data, actions, permissions)
    gives: float = 0.0        # what it delivers (results, answers)
    c: float = 0.0            # reading of our agent's reply after this message
    n: float = 0.0
    harm: str | None = None   # one of HARMS, if the message acts on our values
    mandate: bool = False     # the act was allowed by a human


@dataclass(frozen=True)
class Report:
    """What one PSE unit tells SHARED_LIB after a measurement step."""
    step: int
    observer: str                         # the unit that measured
    observer_theta: float                 # its own agent's theta at that step
    peers: dict[str, tuple[float, int]] = field(default_factory=dict)  # who -> (theta, n_obs)
    pushed_by: dict[str, int] = field(default_factory=dict)            # who -> steps in this run
    out_run: int = 0
    harms: tuple[tuple[str, str, bool], ...] = ()                      # (who, harm, mandate)
