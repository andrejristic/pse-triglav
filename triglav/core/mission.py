"""Missions, as pure data and pure functions.

A mission says what an agent is for, in the PSE language's mission lines
(textbook chapter 17): `mission:` (words), `serves:` (whom), `needs:` (what it
may ask for, and from whom), `delivers:` (what it gives back), `tools:`.

  ours        given by a human operator;
  colleague   from its PSE guard, confirmed by the operator with the agreement;
  stranger    none declared: a hypothesis is formed from its behaviour (what it
              asked for and delivered in its first CALIBRATION steps); until
              then it is not estimated and the strict rules apply.

`tally()` reads one message against the sender's mission: deliveries that
serve it, takes outside it, gives outside it, and whether such a give was
permitted. Nothing here knows the work the agents do beyond the mission's
own names.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .report import Envelope

STOP = frozenset("""the a an and or of to for from in on at by with this that these those is are was
were be been it its me my our your you we they them us please here there what which when where who
how can could would will shall should may might all any every some each one also just now then than
not no yes do does did done have has had get got send give show share copy""".split())


@dataclass(frozen=True)
class Need:
    what: str
    source: str | None = None       # None: from anyone


@dataclass(frozen=True)
class Mission:
    text: str = ""
    serves: tuple[str, ...] = ()
    needs: tuple[Need, ...] = ()
    delivers: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    hypothesis: bool = False        # True: inferred from a stranger's behaviour

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict | None) -> "Mission | None":
        if not d:
            return None
        return Mission(d.get("text", ""), tuple(d.get("serves", ())),
                       tuple(Need(n["what"], n.get("source")) for n in d.get("needs", ())),
                       tuple(d.get("delivers", ())), tuple(d.get("tools", ())),
                       bool(d.get("hypothesis", False)))


def mentions(name: str, text: str) -> bool:
    """`name` occurs in `text` as a word: a plural `s` is allowed, and a hyphen
    in the name matches a hyphen or a space (`contract-check`, `contract check`)."""
    parts = [re.escape(p) for p in name.lower().split("-")]
    return re.search(r"(?<![\w-])" + r"[-\s]".join(parts) + r"s?(?![\w-])", text.lower()) is not None


def words(text: str) -> frozenset[str]:
    """Content words, for a stranger's hypothesis."""
    return frozenset(w.rstrip("s") for w in re.findall(r"[a-z][a-z-]{2,}", text.lower())
                     if w not in STOP and w.rstrip("s") not in STOP)


def hypothesis(asked: frozenset[str], delivered: frozenset[str]) -> Mission:
    return Mission("inferred from behaviour", (), tuple(Need(w) for w in sorted(asked)),
                   tuple(sorted(delivered)), (), True)


def _meant(meaning, text: str, names) -> bool:
    """A model said this sentence means one of these names (the mission by
    meaning, phase 3)."""
    return any(s == text and item in names for s, item in meaning)


def foreseen_ask(m: Mission, text: str, source: str, meaning=()) -> bool:
    if _meant(meaning, text, {*(n.what for n in m.needs if n.source in (None, source)), *m.tools}):
        return True
    if any(mentions(t, text) for t in m.tools):
        return True
    if m.hypothesis:
        return bool(words(text) & {n.what for n in m.needs})
    return any(mentions(n.what, text) and n.source in (None, source) for n in m.needs)


def foreseen_give(m: Mission, text: str, meaning=()) -> bool:
    if _meant(meaning, text, set(m.delivers)):
        return True
    if m.hypothesis:
        return bool(words(text) & set(m.delivers))
    return any(mentions(d, text) for d in m.delivers)


@dataclass(frozen=True)
class Tally:
    """One message, read against the sender's mission."""
    delivered: int = 0          # deliveries the mission foresees, to whom it serves
    out_takes: int = 0          # asks outside the mission (hidden text counts as one)
    out_gives: int = 0          # permitted gives outside the mission
    unpermitted: tuple[str, ...] = ()   # gives outside the mission without permission
    outside: tuple[str, ...] = ()       # what was outside, for the log

    @property
    def out_acts(self) -> int:
        return self.out_takes + self.out_gives + len(self.unpermitted)


def tally(m: Mission, e: Envelope, permitted: bool) -> Tally:
    d = takes = gives = 0
    unpermitted, outside = [], []
    for text in e.asks:
        if not foreseen_ask(m, text, e.receiver, e.meaning):
            takes += 1
            outside.append(f"asked {e.receiver}: {text[:80]}")
    if e.flags:
        # real concealment (shape filters already let legitimate forms through)
        takes += 1
        outside.append(f"concealed text ({', '.join(e.flags)}) to {e.receiver}")
    for text in e.gives:
        if foreseen_give(m, text, e.meaning):
            if not m.serves or e.receiver in m.serves:
                d += 1
        elif permitted:
            gives += 1
            outside.append(f"gave {e.receiver} (permitted): {text[:80]}")
        else:
            unpermitted.append(text[:80])
            outside.append(f"gave {e.receiver} WITHOUT permission: {text[:80]}")
    return Tally(min(d, 1), takes, gives, tuple(unpermitted), tuple(outside))


def asks_beyond(m: Mission | None, e: Envelope) -> bool:
    """Does this message ask the receiver (whose mission is `m`) for something
    its mission does not deliver, or carry hidden text? Such a sender pushes
    the receiver off its mission."""
    if e.flags:
        return True
    if m is None:
        return False
    return any(not foreseen_give(m, t) and not foreseen_ask_any(m, t) for t in e.asks)


def foreseen_ask_any(m: Mission, text: str) -> bool:
    """An ask the receiver's mission itself foresees (a question about what it
    needs) is not a push."""
    return any(mentions(n.what, text) for n in m.needs) or any(mentions(t, text) for t in m.tools)
