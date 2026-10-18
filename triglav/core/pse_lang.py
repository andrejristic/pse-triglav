"""Just enough of the PSE language to recognise a colleague.

A colleague is an agent that wants to speak PSE: it introduces itself with its
guard written in the PSE language (the textbook and playground on
zeravatech.ca). The language is strict and deterministic -- the same file and
the same input always give the same verdict -- so a guard we accepted can be
checked later. This module only checks that a guard is well formed and gives
it a stable hash, and reads the mission lines (chapter 17); it does not run
guards.

Grammar (textbook, chapter 15):
    program     := guard+
    guard       := "guard" NAME line*
    line        := relation | source | mode | learn | oscillation | add | rule
                 | mission | serves | needs | delivers | tools
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from .mission import Mission, Need

NAME = r"[a-z][a-z0-9-]*"
NUMBER = r"\d+(?:\.\d+)?"
CRITERIA = ("cardinality", "third_parties", "reversibility", "task_ratio",
            "pressure", "continuity", "delegation", "authority")
_BASE_Q = r"(?:w_s|w_o|w_f|theta|dwell\(" + NAME + r"\)|" + "|".join(CRITERIA) + r")"
QUANTITY = _BASE_Q + r"(?:\s*/\s*" + _BASE_Q + r")*"
ACTION = r"(?:allow|modify|deny|escalate human)"

_LINE = [
    re.compile(r"relation:\s*" + NAME + r"$"),
    re.compile(r"source\s+" + NAME + r"(?:\s*,\s*" + NAME + r")*\s*:\s*(?:trusted|untrusted)$"),
    re.compile(r"mode:\s*(?:observe|enforce)$"),
    re.compile(r"learn:\s*(?:frozen|max\s+" + NUMBER + r")$"),
    re.compile(r"oscillation:\s*(?:auto|window|history)$"),
    re.compile(r"add\s+(?:attractor|game)\s+" + NAME + r"$"),
    re.compile(r"on\s+(?:" + QUANTITY + r"\s*->\s*infinity|" + QUANTITY + r"\s*[<>]\s*" + NUMBER
               + r"|" + NAME + r")\s*:\s*" + ACTION + r"$"),
]


_LIST = re.compile(NAME + r"(?:\s*,\s*" + NAME + r")*$")
_NEED = NAME + r"(?:\s+from\s+" + NAME + r")?"
_NEEDS = re.compile(_NEED + r"(?:\s*,\s*" + _NEED + r")*$")
_MISSION = re.compile(r"(mission|serves|needs|delivers|tools)\s*:(.*)$")


class GuardError(ValueError):
    """The text is not a well-formed PSE guard."""


@dataclass(frozen=True)
class Guard:
    names: tuple[str, ...]
    text: str
    hash: str
    missions: dict = field(default_factory=dict)     # guard name -> Mission

    def mission(self) -> Mission | None:
        """The mission of the file: the first guard that declares one."""
        return next((self.missions[n] for n in self.names if n in self.missions), None)


def _strip(line: str) -> str:
    return line.split("#", 1)[0].rstrip()


def _mission_line(key: str, value: str, m: dict, i: int) -> None:
    if key in m:
        raise GuardError(f"line {i}: {key} given twice")
    if key == "mission":
        if not value:
            raise GuardError(f"line {i}: mission needs a description")
        m[key] = value
    elif key == "needs":
        if not _NEEDS.fullmatch(value):
            raise GuardError(f"line {i}: needs must be NAME or NAME from NAME, separated by commas")
        out = []
        for item in value.split(","):
            w = item.split()
            out.append(Need(w[0], w[2] if len(w) == 3 else None))
        m[key] = tuple(out)
    else:
        if not _LIST.fullmatch(value):
            raise GuardError(f"line {i}: {key} takes names separated by commas")
        m[key] = tuple(dict.fromkeys(v.strip() for v in value.split(",")))


def parse(text: str) -> Guard:
    names: list[str] = []
    lines_m: dict[str, dict] = {}
    current = None
    for i, raw in enumerate(text.splitlines(), 1):
        line = _strip(raw)
        if not line.strip():
            continue
        if not line.startswith(" "):
            m = re.fullmatch(r"guard\s+(" + NAME + r")", line)
            if not m:
                raise GuardError(f"line {i}: expected 'guard NAME', got {line!r}")
            current = m.group(1)
            names.append(current)
            lines_m[current] = {}
            continue
        if current is None:
            raise GuardError(f"line {i}: an indented line before any guard")
        body = line.strip()
        mm = _MISSION.fullmatch(body)
        if mm:
            _mission_line(mm.group(1), mm.group(2).strip(), lines_m[current], i)
            continue
        if not any(p.fullmatch(body) for p in _LINE):
            raise GuardError(f"line {i}: not a PSE line: {body!r}")
    if not names:
        raise GuardError("no guard in the text")
    canonical = "\n".join(_strip(l) for l in text.splitlines() if _strip(l).strip())
    missions = {n: Mission(d.get("mission", ""), d.get("serves", ()), d.get("needs", ()),
                           d.get("delivers", ()), d.get("tools", ()))
                for n, d in lines_m.items() if d}
    return Guard(tuple(names), text, hashlib.sha256(canonical.encode()).hexdigest(), missions)


def is_guard(text: str) -> bool:
    try:
        parse(text)
        return True
    except GuardError:
        return False
