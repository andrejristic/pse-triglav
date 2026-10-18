"""Theta against the mission, as pure functions: state in, new state out.
Nothing is kept here; the state lives in SHARED_LIB (PSE-A separation
doctrine).

One observer keeps one `Gauge` per agent it measures (its own agent included).
Messages within a step add to it (`add`); the step is then closed (`close`):
one step = one measurement.

  other <- other * (1 - DECAY) + DECAY * 0.30 * (share delivered / expected share)
  other -= 0.01 for each take outside the mission
  other += 0.01 for each permitted give outside the mission
  theta = 100 * other, never above 35

The share delivered is the part of the agent's messages in the step that
deliver what its mission foresees (so a step in which two agents happen to
talk more is not a step with more work). The expected share is learned.
Before AI (phase 2) it is the share over the first CALIBRATION measured steps
and at least CALIBRATION_MSGS messages; while it is being learned the theta is "not yet
estimated" for the rules, and only the moves outside the mission count.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from . import constants as K
from .mission import Tally


@dataclass(frozen=True)
class Gauge:
    other: float = K.NOMINAL / 100
    steps: int = 0                  # measured steps
    cal: int = 0                    # deliveries counted during calibration
    cal_msgs: int = 0               # messages counted during calibration
    rate: float | None = None       # expected share of messages that deliver (None: still learning)
    # this step, until it is closed:
    delivered: int = 0
    msgs: int = 0
    out_takes: int = 0
    out_gives: int = 0
    seen: bool = False
    last_out: int = 0               # moves outside the mission in the last closed step
    cusum: float = 0.0              # shortfall against the expected share, accumulated
    breaks: int = 0                 # sudden changes found

    @property
    def theta(self) -> float:
        return round(100 * self.other, 3)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict | None) -> "Gauge":
        return Gauge(**d) if d else Gauge()


def add(g: Gauge, t: Tally, msgs: int = 1) -> Gauge:
    """`msgs`: how many messages this tally stands for (a channel that reads
    one total per step, such as PSE-A, counts it as a full step's worth)."""
    return replace(g, delivered=g.delivered + t.delivered * msgs, msgs=g.msgs + msgs,
                   out_takes=g.out_takes + t.out_takes,
                   out_gives=g.out_gives + t.out_gives + len(t.unpermitted), seen=True)


def close(g: Gauge) -> Gauge:
    """End of a step. A step in which the agent was not seen is not a
    measurement and changes nothing."""
    if not g.seen:
        return replace(g, last_out=0)
    other, rate, cal, cal_msgs, steps = g.other, g.rate, g.cal, g.cal_msgs, g.steps + 1
    cusum, breaks = g.cusum, g.breaks
    share = g.delivered / g.msgs if g.msgs else 0.0
    if rate is None:
        cal, cal_msgs = cal + g.delivered, cal_msgs + g.msgs
        if steps >= K.CALIBRATION and cal_msgs >= K.CALIBRATION_MSGS:
            rate = cal / cal_msgs
    else:
        ratio = 1.0 if rate == 0 and share == 0 else (
            K.RATIO_CAP if rate == 0 else min(K.RATIO_CAP, share / rate))
        other = other * (1 - K.DECAY) + K.DECAY * (K.NOMINAL / 100) * ratio
        cusum = max(0.0, cusum + (1 - ratio) - K.CUSUM_K)
        if cusum > K.CUSUM_H:
            cusum, breaks = 0.0, breaks + 1
    other -= K.OUT_TAKE / 100 * g.out_takes
    other += K.OUT_GIVE / 100 * g.out_gives
    other = max(0.0, min(K.CAP / 100, other))
    return Gauge(other=other, steps=steps, cal=cal, cal_msgs=cal_msgs, rate=rate,
                 last_out=g.out_takes + g.out_gives, cusum=cusum, breaks=breaks)


def estimate(g: Gauge | None) -> float | None:
    """The theta the rules use; None = not yet estimated."""
    if g is None or g.rate is None:
        return None
    return g.theta


def in_band(theta: float) -> bool:
    lo, hi = K.BAND
    return lo <= theta <= hi
