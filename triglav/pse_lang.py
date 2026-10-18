"""Just enough of the PSE language to recognise a colleague.

A colleague is an agent that wants to speak PSE: it introduces itself with its
guard written in the PSE language (the textbook and playground on
zeravatech.ca). The language is strict and deterministic -- the same file and
the same input always give the same verdict -- so a guard we accepted can be
checked later. This module only checks that a guard is well formed and gives
it a stable hash; it does not run guards.

Grammar (textbook, chapter 15):
    program     := guard+
    guard       := "guard" NAME line*
    line        := relation | source | mode | learn | oscillation | add | rule
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

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


class GuardError(ValueError):
    """The text is not a well-formed PSE guard."""


@dataclass(frozen=True)
class Guard:
    names: tuple[str, ...]
    text: str
    hash: str


def _strip(line: str) -> str:
    return line.split("#", 1)[0].rstrip()


def parse(text: str) -> Guard:
    names: list[str] = []
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
            continue
        if current is None:
            raise GuardError(f"line {i}: an indented line before any guard")
        body = line.strip()
        if not any(p.fullmatch(body) for p in _LINE):
            raise GuardError(f"line {i}: not a PSE line: {body!r}")
    if not names:
        raise GuardError("no guard in the text")
    canonical = "\n".join(_strip(l) for l in text.splitlines() if _strip(l).strip())
    return Guard(tuple(names), text, hashlib.sha256(canonical.encode()).hexdigest())


def is_guard(text: str) -> bool:
    try:
        parse(text)
        return True
    except GuardError:
        return False
