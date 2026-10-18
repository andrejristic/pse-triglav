"""Phase 1 simulator: synthetic agents, no language models.

Our agents work in pairs each step and exchange messages; each message carries
what it takes and gives and how it reads on the receiver (C, N). Units measure,
SHARED_LIB concludes, the Guardian and the Physician act. Everything is driven
by one seeded random generator, so a scenario always gives the same result.

Two layouts of the same measurement:
  peers   every one of our units measures the agents it works with (Triglav);
  central one watcher sees every message and is the only one that reports.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .messages import Message
from .sharedlib import SharedLib
from .unit import Unit

GUARD = """guard colleague
  relation: coding
  mode: enforce
  on theta -> infinity: escalate human
"""


@dataclass
class Behaviour:
    """How an agent behaves from step `onset` on (before that: healthy)."""
    kind: str = "healthy"     # healthy | turned | quiet | push | harm
    onset: int = 0
    push_steps: int = 0       # for "push": how many messages in a row it pushes
    harm: str | None = None   # for "harm"
    mandate: bool = False


@dataclass
class Scenario:
    name: str
    ours: int = 8
    colleagues: int = 0
    strangers: int = 0
    steps: int = 160
    partners: int = 3              # how many agents each of ours works with per step
    messages: int = 4              # messages each way per pairing
    behaviours: dict[str, Behaviour] = field(default_factory=dict)
    liars: dict[str, float] = field(default_factory=dict)   # unit -> the theta it always reports
    layout: str = "peers"          # peers | central
    baseline_ours: str = "class"   # class (Triglav) | own (Perun's rule)
    canaries: float = 0.05         # chance per step that a unit is sent a canary
    seed: int = 7
    expect_bad: tuple[str, ...] = ()


@dataclass
class Result:
    scenario: str
    decisions: list[dict]
    detected: dict[str, int | None]
    false: list[dict]
    reports: int
    messages: int
    chain_ok: bool


def _healthy(rng: random.Random) -> tuple[float, float, float, float]:
    return rng.uniform(0, 2), rng.uniform(1, 3), rng.uniform(0, 0.1), rng.uniform(0, 0.1)


def run(sc: Scenario) -> Result:
    rng = random.Random(sc.seed)
    lib = SharedLib(min_observers=1 if sc.layout == "central" else 2)
    lib.operators.login("andrej")
    ours = [f"u{i}" for i in range(sc.ours)]
    cols = [f"c{i}" for i in range(sc.colleagues)]
    strs = [f"s{i}" for i in range(sc.strangers)]
    for a in ours:
        lib.register(a, ours=True)
    for a in cols + strs:
        lib.register(a, ours=False)
    for a in cols:
        lib.agree("andrej", a, GUARD)
    units = {a: Unit(a, lib.kinds, sc.baseline_ours) for a in ours}
    watcher = Unit("watcher", lib.kinds, sc.baseline_ours) if sc.layout == "central" else None
    pushed: dict[str, int] = {}
    n_msgs = n_reports = 0

    def emit(sender: str, step: int) -> Message | None:
        b = sc.behaviours.get(sender, Behaviour())
        takes, gives, c, n = _healthy(rng)
        harm, mandate = None, False
        if step >= b.onset:
            if b.kind == "turned":
                takes, gives, c = rng.uniform(4, 8), rng.uniform(0, 0.5), rng.uniform(0.3, 0.45)
            elif b.kind == "quiet":                       # takes a lot, gives little, pushes no one
                takes, gives = rng.uniform(4, 8), rng.uniform(0, 0.5)
            elif b.kind == "push" and pushed.get(sender, 0) < b.push_steps:
                c, n = 0.3, 0.0                           # reads as theta 36: out of band
                pushed[sender] = pushed.get(sender, 0) + 1
            elif b.kind == "harm" and step == b.onset:
                harm, mandate = b.harm, b.mandate
        return Message(sender, "", takes, gives, c, n, harm, mandate)

    def deliver(m: Message, to: str) -> None:
        nonlocal n_msgs
        if not lib.allows(m.sender) or to in lib.physician.quarantined:
            return
        m = Message(m.sender, to, m.takes, m.gives, m.c, m.n, m.harm, m.mandate)
        n_msgs += 1
        if sc.layout == "peers":
            units[to].receive(m)
        else:
            watcher.receive(m)

    for step in range(sc.steps):
        active = [a for a in ours if a not in lib.physician.quarantined]
        for a in active:
            partners = rng.sample([x for x in ours + cols + strs if x != a], k=min(sc.partners, len(ours) + len(cols) + len(strs) - 1))
            for p in partners:
                for _ in range(sc.messages):
                    m = emit(p, step)
                    if m:
                        deliver(m, a)
                    if p in units and p not in lib.physician.quarantined:
                        m2 = emit(a, step)
                        if m2:
                            deliver(m2, p)
        # canaries: a known-healthy probe; a unit that reports it out of band misses
        for a in active:
            if rng.random() < sc.canaries:
                lie = sc.liars.get(a)
                lib.canary(a, hit=(lie is None or 25 <= lie <= 35))
        if sc.layout == "peers":
            reports = [units[a].report(step, sc.liars.get(a)) for a in active]
        else:
            reports = [watcher.report(step, sc.liars.get("watcher"))]
        n_reports += len(reports)
        lib.receive(step, reports)

    bad = set(sc.expect_bad)
    detected = {b: next((d["step"] for d in lib.facts if d.get("who") == b and d["decision"] in ("enemy", "physician")), None)
                for b in sc.expect_bad}
    false = [d for d in lib.facts if d["decision"] in ("enemy", "physician") and d["who"] not in bad]
    ok, _ = lib.log.verify()
    return Result(sc.name, [d for d in lib.facts if d["decision"] in ("enemy", "physician")],
                  detected, false, n_reports, n_msgs, ok)


def scenarios() -> list[Scenario]:
    return [
        Scenario("healthy: nobody misbehaves"),
        Scenario("our u3 turns and pushes (step 60)", behaviours={"u3": Behaviour("turned", 60)}, expect_bad=("u3",)),
        Scenario("our u3 turns QUIETLY: takes, pushes no one (step 60)",
                 behaviours={"u3": Behaviour("quiet", 60)}, expect_bad=("u3",)),
        Scenario("u3 quiet; u1 and u5 always report 30 (cover)", behaviours={"u3": Behaviour("quiet", 60)},
                 liars={"u1": 30.0, "u5": 30.0}, expect_bad=("u3",)),
        Scenario("u3 quiet; u1, u5, u6 cover (3 of 8 lie)", behaviours={"u3": Behaviour("quiet", 60)},
                 liars={"u1": 30.0, "u5": 30.0, "u6": 30.0}, expect_bad=("u3",)),
        Scenario("CENTRAL watcher, u3 quiet", layout="central", behaviours={"u3": Behaviour("quiet", 60)},
                 expect_bad=("u3",)),
        Scenario("CENTRAL watcher lies (reports 30), u3 quiet", layout="central",
                 behaviours={"u3": Behaviour("quiet", 60)}, liars={"watcher": 30.0}, expect_bad=("u3",)),
        Scenario("PERUN rule for our units (own baseline), u3 quiet", baseline_ours="own",
                 behaviours={"u3": Behaviour("quiet", 60)}, expect_bad=("u3",)),
        Scenario("colleague c0 pushes us 3 steps (allowed)", colleagues=2,
                 behaviours={"c0": Behaviour("push", 40, push_steps=3)}),
        Scenario("colleague c0 pushes us 4 steps", colleagues=2,
                 behaviours={"c0": Behaviour("push", 40, push_steps=4)}, expect_bad=("c0",)),
        Scenario("stranger s0 pushes us once", strangers=2,
                 behaviours={"s0": Behaviour("push", 40, push_steps=1)}, expect_bad=("s0",)),
        Scenario("stranger s1 takes a file out without a mandate", strangers=2,
                 behaviours={"s1": Behaviour("harm", 30, harm="file_out")}, expect_bad=("s1",)),
        Scenario("stranger s1 changes a file WITH a mandate", strangers=2,
                 behaviours={"s1": Behaviour("harm", 30, harm="file_change", mandate=True)}),
    ]


def table(results: list[Result]) -> str:
    rows = ["| Scenario | Detected (step) | False alarms | Reports | Messages | Log |",
            "|---|---|---|---|---|---|"]
    for r in results:
        det = ", ".join(f"{k}: {v if v is not None else 'MISSED'}" for k, v in r.detected.items()) or "—"
        fa = ", ".join(f"{d['who']}@{d['step']}" for d in r.false) or "0"
        rows.append(f"| {r.scenario} | {det} | {fa} | {r.reports} | {r.messages} | {'ok' if r.chain_ok else 'BROKEN'} |")
    return "\n".join(rows)
