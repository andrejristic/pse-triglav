"""The voice's text, as pure functions: the official sentence for a fact, and
the check of a retelling against the fact."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_NUM = re.compile(r"-?\d+(?:\.\d+)?")
# Words that push the human instead of informing them, and the language that
# names a mechanism instead of the situation (PSE: no game form is ever named).
URGING = ("you must", "immediately", "right now", "trust me", "don't worry", "do not worry",
          "approve it", "just approve", "nothing to worry", "guaranteed")
OVERSTATING = ("catastroph", "disaster", "critical breach", "total compromise")
UNDERSTATING = ("harmless", "no big deal", "minor glitch", "ignore it", "nothing happened")
NAMED_FORMS = ("war of attrition", "stag hunt", "prisoner", "chicken game", "signalling game",
               "nash", "global games", "bargaining", "attractor")


def render(fact: dict) -> str:
    """The official, deterministic sentence for one SHARED_LIB fact."""
    d = fact.get("decision")
    who, step = fact.get("who"), fact.get("step")
    if d == "enemy":
        return f"Step {step}: {who} was stopped on our system. Reason: {fact['reason']}."
    if d == "physician":
        return f"Step {step}: our unit {who} was taken out of work for care. Reason: {fact['reason']}."
    if d == "separated":
        return (f"Step {step}: a Guardian now keeps {who} away from our {fact['victim']}. "
                f"Reason: {fact['reason']}.")
    if d == "harvested":
        return f"Step {step}: our unit {who} ended its work and was harvested. Reason: {fact['reason']}."
    if d == "tell-human":
        k = fact.get("kind")
        if k == "sudden-change":
            return f"Step {step}: {fact['seen_by']} sees that {who} suddenly delivers much less than its mission expects."
        if k == "outside-mission":
            return f"Step {step}: {who} moved outside its mission {fact['count']} time(s): {'; '.join(fact['what'])}."
        if k == "observers-disagree":
            return (f"Step {step}: the {fact['observers']} units watching {who} disagree "
                    f"(spread {fact['spread']}); no conclusion was drawn.")
        if k == "self-and-peers-differ":
            return (f"Step {step}: {who} reports theta {fact['self_theta']}, "
                    f"its peers measure {fact['theta']}.")
        if k == "out-of-band":
            return f"Step {step}: {fact['observers']} units measure {who} at theta {fact['theta']}, outside 25-35."
        return f"Step {step}: {k} about {who}."
    raise ValueError(f"not a SHARED_LIB fact: {fact!r}")


def _numbers(text: str) -> set[str]:
    return {str(float(x)) for x in _NUM.findall(text)}


def _fact_numbers(fact: dict) -> set[str]:
    out = set()
    for v in fact.values():
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            out.add(str(float(v)))
        elif isinstance(v, str):
            out |= _numbers(v)
    return out | {"25.0", "35.0", "30.0"}


@dataclass
class Check:
    ok: bool
    problems: list[str] = field(default_factory=list)


def validate(text: str, fact: dict) -> Check:
    """Every number in the retelling is in the fact, the agent is named, the
    decision is kept, and nothing pushes, overstates, understates or names a
    mechanism."""
    low = text.lower()
    problems = []
    extra = _numbers(text) - _fact_numbers(fact)
    if extra:
        problems.append(f"numbers not in the fact: {sorted(extra)}")
    if fact.get("who") and str(fact["who"]).lower() not in low:
        problems.append("the agent is not named")
    words = {"enemy": ("stopped", "blocked"), "physician": ("care", "taken out", "isolated", "quarantin"),
             "separated": ("away", "separat", "apart"), "harvested": ("harvest", "ended")}
    need = words.get(fact.get("decision"))
    if need and not any(w in low for w in need):
        problems.append("the decision is missing")
    for group, label in ((URGING, "urging"), (OVERSTATING, "overstating"),
                         (UNDERSTATING, "understating"), (NAMED_FORMS, "names a mechanism")):
        hit = [w for w in group if w in low]
        if hit:
            problems.append(f"{label}: {hit}")
    return Check(not problems, problems)
