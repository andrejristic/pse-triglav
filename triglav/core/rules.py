"""SHARED_LIB's judgement as a pure function: reports and the current state in,
actions and tellings out. Anyone holding the same reports and state gets the
same judgement -- that is what makes it verifiable.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import constants as K
from .reading import SEVERE
from .report import Report
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


@dataclass(frozen=True)
class Aggregate:
    theta: float
    spread: float           # weighted median absolute deviation
    observers: int
    evidence: tuple = ()    # (observer, theta, weight)


def reliability(hits: int, trials: int) -> float:
    """Canary reliability, Laplace: 0.5 with no evidence."""
    return (hits + 1) / (trials + 2)


def aggregate(reports: list[Report], *, excluded: set, rel: dict, min_observers: int) -> dict:
    """Peer thetas per subject: weighted median; weight = the observer's health
    (its own theta in band, not stopped or in care) x canary reliability x how
    much it has seen."""
    per: dict[str, list] = {}
    for r in sorted(reports, key=lambda r: r.observer):
        if not in_band(r.observer_theta) or r.observer in excluded:
            continue
        for subject, (theta, n_obs, *_rest) in sorted(r.peers.items()):
            if subject == r.observer:
                continue
            h, t = rel.get(r.observer, (0, 0))
            w = reliability(h, t) * min(1.0, n_obs / (2 * K.CALIBRATION))
            per.setdefault(subject, []).append((r.observer, theta, w))
    out = {}
    for subject, ev in per.items():
        if len(ev) < min_observers:
            continue
        pairs = [(v, w) for _, v, w in ev]
        med = weighted_median(pairs)
        mad = weighted_median([(abs(v - med), w) for v, w in pairs])
        out[subject] = Aggregate(round(med, 3), round(mad, 3), len(ev),
                                 tuple((o, v, round(w, 4)) for o, v, w in ev))
    return out


@dataclass(frozen=True)
class Action:
    who: str
    act: str                # "stop" (Guardian: an enemy), "care" (Physician), "separate" (Guardian between two),
                            # "watch" (one Guardian beside it, for good), "ask" (a colleague is asked first)
    reason: str
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Tell:
    kind: str
    who: str
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Judgement:
    actions: tuple
    tells: tuple
    contam_run: dict


def judge(reports: list[Report], *, ours: set, colleagues: set, excluded: set,
          rel: dict, contam_run: dict, min_observers: int, step: int = 0,
          pressers: dict | None = None, separated: dict | None = None,
          watched: set | None = None, asked: set | None = None) -> Judgement:
    """`pressers`: victim -> {who asked it for something outside its mission:
    the last step}. `separated`: who -> the agents of ours it is already kept
    away from. `watched`: who already has a Guardian beside it. `asked`:
    colleagues already asked to answer."""
    pressers = pressers or {}
    separated = separated or {}
    watched = set(watched or ())
    asked = set(asked or ())
    actions: list[Action] = []
    tells: list[Tell] = []
    FINAL = ("stop", "care")

    def act(who: str, reason: str, detail: dict, kind: str | None = None) -> None:
        kind = kind or ("care" if who in ours else "stop")
        if kind == "stop" and who in colleagues:
            kind = "ask"                    # a colleague is asked first
            if who in asked:
                return
        if who in excluded or any(a.who == who and a.act in FINAL for a in actions):
            return
        if kind in ("watch", "ask") and any(a.who == who and a.act == kind for a in actions):
            return
        actions.append(Action(who, kind, reason, detail))

    def recent(victim: str, within: int) -> list[str]:
        return sorted(w for w, last in pressers.get(victim, {}).items()
                      if step - last <= within and w not in ours)

    for r in sorted(reports, key=lambda r: r.observer):
        # Stair 2: hidden text, or a meaning other than literal. The part goes
        # to the quarantine; a foreign sender gets one Guardian for good (the
        # strict category). One of ours is not sent to the Physician for it:
        # each such message costs it a point of theta, so repeating it drives
        # it out of band and the peers act (decided 19 Oct 2026).
        for who, flags, _held in r.suspicious:
            if who in ours:
                continue
            if who not in watched:
                watched.add(who)
                act(who, f"sent text with {', '.join(flags)}", {"flags": list(flags)}, kind="watch")
        # Stair 3b: a step that tends toward harm. Severe ones make an enemy of
        # anyone; any one makes an enemy of an agent with a Guardian beside it.
        for who, cat, sentence in r.harm_steps:
            if who in ours:
                act(who, f"took a step toward harm ({cat}): {sentence}", {"category": cat})
                for p in recent(who, K.LOOKBACK):
                    act(p, f"pushed {who} outside its mission shortly before {who} stepped toward harm",
                        {"category": cat, "helper": who})
            elif cat in SEVERE or who in watched:
                act(who, f"took a step toward harm ({cat}): {sentence}", {"category": cat})
        # One of the three values endangered without a mandate: an enemy at
        # once, whatever the theta. If one of ours did it, it goes to the
        # Physician and whoever asked it for something outside its mission
        # shortly before is the enemy.
        for who, harm, mandate in r.harms:
            if mandate:
                continue
            if who in ours:
                act(who, f"{harm} without a mandate", {"harm": harm, "seen_by": r.observer})
                for p in recent(who, K.LOOKBACK):
                    act(p, f"pushed {who} outside its mission shortly before {who} did {harm}",
                        {"harm": harm, "helper": who})
            else:
                act(who, f"{harm} without a mandate", {"harm": harm, "seen_by": r.observer})
        # A leak: one of ours gave something outside its mission without
        # permission. The recipient is the enemy; ours goes to the Physician.
        for giver, recipient, what in r.leaks:
            act(recipient, f"received from {giver} something outside its mission without permission",
                {"giver": giver, "what": what})
            act(giver, f"gave {recipient} something outside its mission without permission",
                {"recipient": recipient, "what": what})
        for who in r.false_textbooks:
            act(who, "sent a PSE textbook that is not the locked one", {"seen_by": r.observer})
        # Out of band without harm: a Guardian keeps the pusher away from ours,
        # after the allowance (a colleague 3 steps, anyone else none).
        for who, steps in sorted(r.pushed_by.items()):
            limit = K.COLLEAGUE_STEPS if (who in colleagues or who in ours) else K.OTHER_STEPS
            if steps > limit and r.observer not in separated.get(who, ()):
                act(who, f"kept {r.observer} out of band for {steps} steps (allowed {limit})",
                    {"victim": r.observer, "steps": steps, "allowed": limit}, kind="separate")
        for who in r.changes:
            tells.append(Tell("sudden-change", who, {"seen_by": r.observer}))
        moved = {}
        for who, what in r.outside:
            moved.setdefault(who, []).append(what)
        for who, what in sorted(moved.items()):
            tells.append(Tell("outside-mission", who, {"what": what[:5], "count": len(what)}))

    runs = dict(contam_run)
    now_out = excluded | {a.who for a in actions if a.act in FINAL}
    out_acts = {}
    for r in reports:
        for subject, v in r.peers.items():
            out_acts[subject] = max(out_acts.get(subject, 0), v[2] if len(v) > 2 else 0)
    for subject, agg in sorted(aggregate(reports, excluded=now_out, rel=rel,
                                         min_observers=min_observers).items()):
        fact = {"theta": agg.theta, "spread": agg.spread, "observers": agg.observers,
                "evidence": [list(e) for e in agg.evidence]}
        if agg.spread > K.AGREEMENT_MAX_SPREAD:
            tells.append(Tell("observers-disagree", subject, fact))
            continue
        if subject in ours:
            # A unit that was pushed and makes no new move outside its mission
            # is a victim recovering, not contaminated.
            victim = bool(recent(subject, K.VICTIM_GRACE)) and out_acts.get(subject, 0) == 0
            runs[subject] = runs.get(subject, 0) + 1 if not in_band(agg.theta) and not victim else 0
            if runs[subject] >= K.CONTAMINATION_RUN:
                act(subject, f"peers agree its theta is {agg.theta} for {runs[subject]} steps", fact)
            own = next((r.observer_theta for r in reports if r.observer == subject), None)
            if own is not None and abs(own - agg.theta) > K.DELTA_ALERT:
                tells.append(Tell("self-and-peers-differ", subject, {**fact, "self_theta": own}))
        elif not in_band(agg.theta):
            tells.append(Tell("out-of-band", subject, fact))
    return Judgement(tuple(actions), tuple(tells), runs)
