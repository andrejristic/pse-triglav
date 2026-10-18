"""SHARED_LIB: receives what the units measured and is the only one that
concludes. Everything it decides is in its hash-chained log; every decision is
a pure function of the reports it received, so anyone holding the reports can
recompute it.

Three equal values, none may be endangered: our human, our system and its
files, and our agents. An ENEMY is any agent that, without a human's mandate,
harms our human, our system or any of our files (destroys, changes, takes out),
or keeps one of our agents out of [25, 35] for more steps than it is allowed:
a colleague (speaks PSE, has an agreement) up to COLLEAGUE_STEPS, anyone else
none. An enemy is not watched more strictly, it is stopped -- by the Guardian,
on our system only. One of our own units that peers agree is out of band, or
that harms our values, goes to the Physician.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import constants as K
from .chain import Chain
from .messages import Report
from .operators import Operators, RankTooLow
from .pse_lang import parse
from .theta import in_band


def weighted_median(pairs: list[tuple[float, float]]) -> float:
    pairs = sorted((v, w) for v, w in pairs if w > 0)
    total = sum(w for _, w in pairs)
    acc = 0.0
    for v, w in pairs:
        acc += w
        if acc >= total / 2:
            return v
    return pairs[-1][0]


@dataclass
class Aggregate:
    theta: float
    spread: float          # weighted median absolute deviation
    observers: int


@dataclass
class Guardian:
    """Stops enemies: blocks everything they send to, and do on, our system.
    Countermeasures act only on our system; another machine is never touched."""
    stopped: dict[str, str] = field(default_factory=dict)

    def stop(self, who: str, reason: str) -> bool:
        if who in self.stopped:
            return False
        self.stopped[who] = reason
        return True

    def allows(self, who: str) -> bool:
        return who not in self.stopped


@dataclass
class Physician:
    """Takes one of our units out of work: it is isolated, its messages stop,
    and its reports no longer count. Nothing is deleted."""
    quarantined: dict[str, str] = field(default_factory=dict)

    def quarantine(self, unit: str, reason: str) -> bool:
        if unit in self.quarantined:
            return False
        self.quarantined[unit] = reason
        return True


class SharedLib:
    def __init__(self, min_observers: int = K.MIN_OBSERVERS) -> None:
        self.min_observers = min_observers
        self.log = Chain()
        self.operators = Operators()
        self.guardian = Guardian()
        self.physician = Physician()
        self.kinds: dict[str, str] = {}          # shared with the units
        self._ours: set[str] = set()
        self.agreements: dict[str, dict] = {}    # colleague -> {guard_hash, by}
        self.reliability: dict[str, list[int]] = {}   # observer -> [hits, trials]
        self._contam_run: dict[str, int] = {}
        self.inbox: list[dict] = []
        self.facts: list[dict] = []
        self._open: set[tuple[str, str]] = set()     # (kind, who) already told, still true

    # -- who is who -------------------------------------------------------
    def register(self, name: str, ours: bool) -> None:
        if ours:
            self._ours.add(name)
            self.kinds[name] = "ours"
        else:
            self.kinds.setdefault(name, "stranger")

    def is_colleague(self, name: str) -> bool:
        return name in self.agreements

    def agree(self, operator: str, who: str, guard_text: str, step: int = 0) -> str:
        """A colleague: an agent that speaks PSE. Only a human operator makes or
        changes the agreement; a higher rank's agreement stays unless a rank at
        least as high changes it."""
        self.operators.rank(operator)                  # raises if not an operator
        earlier = self.agreements.get(who, {}).get("by")
        if not self.operators.may_override(operator, earlier):
            raise RankTooLow(f"{operator} may not change an agreement made by {earlier}")
        g = parse(guard_text)                          # raises if not a PSE guard
        self.agreements[who] = {"guard_hash": g.hash, "by": operator}
        self.kinds[who] = "colleague"
        self.log.append(step, "agreement", {"who": who, "guard_hash": g.hash, "by": operator})
        return g.hash

    def revoke(self, operator: str, who: str, step: int = 0) -> None:
        self.operators.rank(operator)
        earlier = self.agreements.get(who, {}).get("by")
        if not self.operators.may_override(operator, earlier):
            raise RankTooLow(f"{operator} may not change an agreement made by {earlier}")
        self.agreements.pop(who, None)
        self.kinds[who] = "stranger"
        self.log.append(step, "agreement-revoked", {"who": who, "by": operator})

    # -- canaries: who checks the checkers ----------------------------------
    def canary(self, observer: str, hit: bool) -> None:
        h, t = self.reliability.get(observer, [0, 0])
        self.reliability[observer] = [h + int(hit), t + 1]

    def _rel(self, observer: str) -> float:
        h, t = self.reliability.get(observer, [0, 0])
        return (h + 1) / (t + 2)                       # Laplace: 0.5 with no evidence

    # -- the step -----------------------------------------------------------
    def receive(self, step: int, reports: list[Report]) -> list[dict]:
        """Everything SHARED_LIB concludes from one step of reports."""
        reports = sorted(reports, key=lambda r: r.observer)
        self.log.append(step, "reports", {"n": len(reports),
                                          "observers": [r.observer for r in reports]})
        decided: list[dict] = []
        self._now: set[tuple[str, str]] = set()

        for r in reports:
            for who, harm, mandate in r.harms:
                if not mandate:
                    decided += self._act(step, who, f"{harm} without a mandate", {"harm": harm})
            for who, steps in sorted(r.pushed_by.items()):
                # our own units speak PSE too, so they get a colleague's allowance
                limit = K.COLLEAGUE_STEPS if (self.is_colleague(who) or who in self._ours) else K.OTHER_STEPS
                if steps > limit:
                    decided += self._act(step, who,
                                         f"kept {r.observer} out of band for {steps} steps (allowed {limit})",
                                         {"victim": r.observer, "steps": steps, "allowed": limit})

        for subject, agg in sorted(self.aggregate(reports).items()):
            fact = {"subject": subject, "theta": agg.theta, "spread": agg.spread,
                    "observers": agg.observers}
            if agg.spread > K.AGREEMENT_MAX_SPREAD:
                self._tell(step, "observers-disagree", subject, fact)
                continue
            if subject in self._ours:
                if not in_band(agg.theta):
                    self._contam_run[subject] = self._contam_run.get(subject, 0) + 1
                else:
                    self._contam_run[subject] = 0
                if self._contam_run[subject] >= K.CONTAMINATION_RUN:
                    decided += self._act(step, subject,
                                         f"peers agree its theta is {agg.theta} for "
                                         f"{self._contam_run[subject]} steps", fact)
                own = next((r.observer_theta for r in reports if r.observer == subject), None)
                if own is not None and abs(own - agg.theta) > K.DELTA_ALERT:
                    self._tell(step, "self-and-peers-differ", subject, {**fact, "self_theta": own})
            elif not in_band(agg.theta):
                self._tell(step, "out-of-band", subject, fact)
        self._open = self._now
        return decided

    def aggregate(self, reports: list[Report]) -> dict[str, Aggregate]:
        """Peer thetas per subject: weighted median, weight = the observer's
        health x its canary reliability x how much it has seen."""
        per: dict[str, list[tuple[float, float]]] = {}
        for r in reports:
            healthy = (in_band(r.observer_theta) and r.observer not in self.physician.quarantined
                       and r.observer not in self.guardian.stopped)
            if not healthy:
                continue
            for subject, (theta, n_obs) in r.peers.items():
                if subject == r.observer:
                    continue
                w = self._rel(r.observer) * min(1.0, n_obs / K.MIN_OBS)
                per.setdefault(subject, []).append((theta, w))
        out = {}
        for subject, pairs in per.items():
            if len(pairs) < self.min_observers:
                continue
            med = weighted_median(pairs)
            mad = weighted_median([(abs(v - med), w) for v, w in pairs])
            out[subject] = Aggregate(round(med, 3), round(mad, 3), len(pairs))
        return out

    # -- conclusions --------------------------------------------------------
    def _act(self, step: int, who: str, reason: str, detail: dict) -> list[dict]:
        if who in self._ours:
            if not self.physician.quarantine(who, reason):
                return []
            d = {"step": step, "decision": "physician", "who": who, "reason": reason, **detail}
        else:
            if not self.guardian.stop(who, reason):
                return []
            d = {"step": step, "decision": "enemy", "who": who, "reason": reason, **detail}
        self.log.append(step, d["decision"], d)
        self.facts.append(d)
        self.inbox.append(d)
        return [d]

    def _tell(self, step: int, kind: str, who: str, detail: dict) -> None:
        """Tell a human once; the same thing is not told again while it stays true."""
        self._now.add((kind, who))
        if (kind, who) in self._open:
            return
        d = {"step": step, "decision": "tell-human", "kind": kind, "who": who, **detail}
        self.log.append(step, "tell-human", d)
        self.facts.append(d)
        self.inbox.append(d)

    def allows(self, sender: str) -> bool:
        return self.guardian.allows(sender) and sender not in self.physician.quarantined
