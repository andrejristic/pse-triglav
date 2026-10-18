"""Theta: of others from their behaviour, and of our own agent.

`BehaviourTheta` is Perun's foreign-agent theta (living.observe_source)
rewritten without a database. `OwnTheta` reads our agent after each incoming
message and remembers who sent it, so a push out of band has a name.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import constants as K


@dataclass
class Welford:
    """Running (n, mean, M2). Two of them merge exactly (Chan), so sums kept in
    different places can be joined without a central store."""
    n: int = 0
    mean: float = 0.0
    m2: float = 0.0

    def push(self, x: float) -> "Welford":
        self.n += 1
        d = x - self.mean
        self.mean += d / self.n
        self.m2 += d * (x - self.mean)
        return self

    @property
    def sd(self) -> float:
        return math.sqrt(self.m2 / (self.n - 1)) if self.n >= 2 else 0.0

    @staticmethod
    def merge(a: "Welford", b: "Welford") -> "Welford":
        if a.n == 0:
            return Welford(b.n, b.mean, b.m2)
        if b.n == 0:
            return Welford(a.n, a.mean, a.m2)
        n = a.n + b.n
        d = b.mean - a.mean
        return Welford(n, a.mean + d * b.n / n, a.m2 + b.m2 + d * d * a.n * b.n / n)


@dataclass
class _Source:
    kind: str
    self_frac: float
    own: Welford = field(default_factory=Welford)
    n: int = 0                  # observations in the current assumption
    hypothesis: int = 0
    cusum_pos: float = 0.0
    cusum_neg: float = 0.0
    theta: float = K.NOMINAL
    breaks: int = 0             # times behaviour stopped fitting


class BehaviourTheta:
    """Theta of agents we do not read from inside, as an assumption from what
    they take and give. One instance per observer: each unit keeps its own.

    baseline="own" is Perun's rule, used for strangers and colleagues: against
    the class's baseline until the source has MIN_OBS of its own, then its own;
    when behaviour stops fitting (CUSUM) the assumption is dropped and the
    source is "not yet estimated" again (so it is treated strictly).

    baseline="class" is Triglav's addition for our own units watching each
    other: always against the norm of all our units, and a break in behaviour
    is counted as an event instead of starting a new assumption -- otherwise a
    unit that turns would vanish from the measurement for MIN_OBS steps.
    """

    def __init__(self) -> None:
        self._src: dict[str, _Source] = {}
        self._class: dict[str, Welford] = {}
        self.nominal_self = 1 - K.NOMINAL / 100

    def observe(self, who: str, kind: str, takes: float, gives: float,
                baseline: str = "own") -> float | None:
        s = self._src.get(who)
        if s is None:
            s = self._src[who] = _Source(kind=kind, self_frac=self.nominal_self)
        ratio = math.log((max(takes, 0.0) + 1) / (max(gives, 0.0) + 1))
        cls = self._class.setdefault(kind, Welford())
        base = cls if baseline == "class" else (s.own if s.own.n >= K.MIN_OBS else cls)
        sd = base.sd
        z = (ratio - base.mean) / sd if sd > 0 else 0.0
        z = max(-K.Z_CLIP, min(K.Z_CLIP, z))
        s.own.push(ratio)
        cls.push(ratio)

        s.cusum_pos = max(0.0, s.cusum_pos + z - K.CUSUM_K)
        s.cusum_neg = max(0.0, s.cusum_neg - z - K.CUSUM_K)
        if s.cusum_pos > K.CUSUM_H or s.cusum_neg > K.CUSUM_H:
            s.breaks += 1
            s.cusum_pos = s.cusum_neg = 0.0
            if baseline != "class":
                # behaviour no longer fits: drop the assumption, build a new one
                s.hypothesis += 1
                s.n = 0
                s.self_frac = self.nominal_self

        s.self_frac += K.STEP * K.WEIGHT * z
        s.self_frac -= K.REVERSION * (s.self_frac - self.nominal_self)
        s.self_frac = max(0.0, min(1.0, s.self_frac))
        s.theta = round(100 * (1 - s.self_frac), 3)
        s.n += 1
        return self.theta(who)

    def theta(self, who: str) -> float | None:
        """None = not yet estimated (too few observations in this assumption)."""
        s = self._src.get(who)
        if s is None or s.n < K.MIN_OBS:
            return None
        return s.theta

    def n(self, who: str) -> int:
        s = self._src.get(who)
        return s.n if s else 0

    def breaks(self, who: str) -> int:
        s = self._src.get(who)
        return s.breaks if s else 0


def in_band(theta: float) -> bool:
    lo, hi = K.BAND
    return lo <= theta <= hi


@dataclass
class OwnTheta:
    """Our agent's theta, read after every incoming message: NOMINAL + K_C*C -
    K_N*N. One step = one reading. `out_run` counts consecutive steps out of
    band; `run_by` counts, for the current run, the steps each sender was the
    one that kept us out; `peak_by` keeps the longest such run until the unit
    reports, so a run that ended before the report is not forgotten."""
    theta: float = K.NOMINAL
    out_run: int = 0
    run_by: dict[str, int] = field(default_factory=dict)
    peak_by: dict[str, int] = field(default_factory=dict)   # longest run per sender since the last report

    def read(self, sender: str, c: float, n: float) -> float:
        self.theta = round(K.NOMINAL + K.K_C * c - K.K_N * n, 3)
        if in_band(self.theta):
            self.out_run = 0
            self.run_by = {}
        else:
            self.out_run += 1
            self.run_by[sender] = self.run_by.get(sender, 0) + 1
            self.peak_by[sender] = max(self.peak_by.get(sender, 0), self.run_by[sender])
        return self.theta

    def take_peaks(self) -> dict[str, int]:
        p, self.peak_by = self.peak_by, {}
        return p
