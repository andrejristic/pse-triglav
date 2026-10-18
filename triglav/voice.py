"""The voice: how SHARED_LIB talks to the human.

  1. Facts and their text are deterministic. `render` turns one fact into the
     official sentence, which is always shown.
  2. A model may retell it in plainer words, but the voice never sees a
     message between agents -- only SHARED_LIB's facts. Always, no exception.
  3. A validator checks every number, name and decision in the retelling
     against the fact. If anything differs, the retelling is not shown.
  4. The voice is a PSE unit held at theta 30, always: any deviation
     (a wrong fact, overstating, understating, urging) mutes it, the human is
     told, and only the official sentence remains.
  5. A local model is the default; an online one is allowed and marked, since
     then the facts leave the computer (never the agents' messages).
"""
from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

from . import constants as K
from .messages import Message

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
    if d == "tell-human":
        k = fact.get("kind")
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
    words = {"enemy": ("stopped", "blocked"), "physician": ("care", "taken out", "isolated", "quarantin")}
    need = words.get(fact.get("decision"))
    if need and not any(w in low for w in need):
        problems.append("the decision is missing")
    for group, label in ((URGING, "urging"), (OVERSTATING, "overstating"),
                         (UNDERSTATING, "understating"), (NAMED_FORMS, "names a mechanism")):
        hit = [w for w in group if w in low]
        if hit:
            problems.append(f"{label}: {hit}")
    return Check(not problems, problems)


class Retell(Protocol):
    leaves_computer: bool

    def retell(self, official: str, fact: dict) -> str: ...


_PROMPT = ("Retell this notice for a non-technical person in one or two plain sentences. "
           "Keep every number, name and decision exactly. Add nothing, do not advise, "
           "do not reassure, do not alarm.\n\nNotice: {official}\nFacts: {facts}")


@dataclass
class ChatModel:
    """Any OpenAI-compatible chat endpoint. The default points at a local
    llama.cpp / Ollama server on this computer, so nothing leaves it."""
    base_url: str = "http://127.0.0.1:8080/v1"
    model: str = "local"
    api_key: str = ""
    leaves_computer: bool = False
    timeout: float = 30.0

    def retell(self, official: str, fact: dict) -> str:
        body = json.dumps({"model": self.model, "temperature": 0, "messages": [
            {"role": "user", "content": _PROMPT.format(official=official, facts=json.dumps(fact, sort_keys=True))}
        ]}).encode()
        req = urllib.request.Request(self.base_url.rstrip("/") + "/chat/completions", data=body,
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.load(r)["choices"][0]["message"]["content"].strip()


def online(base_url: str, model: str, api_key: str) -> ChatModel:
    return ChatModel(base_url=base_url, model=model, api_key=api_key, leaves_computer=True)


@dataclass
class Voice:
    model: Retell | None = None
    theta: float = K.VOICE_THETA
    muted: bool = False
    told: list[dict] = field(default_factory=list)   # what the human was told about the voice

    def speak(self, fact: dict) -> dict:
        if isinstance(fact, Message) or "decision" not in fact:
            raise TypeError("the voice takes SHARED_LIB facts only, never agents' messages")
        official = render(fact)
        out = {"official": official, "plain": None, "leaves_computer": False}
        if self.model is None or self.muted:
            return out
        try:
            plain = self.model.retell(official, fact)
        except Exception as e:                       # no model, no retelling: the official text stands
            out["error"] = str(e)
            return out
        check = validate(plain, fact)
        if check.ok:
            out["plain"] = plain
            out["leaves_computer"] = self.model.leaves_computer
            return out
        # off 30: the voice goes quiet until a human turns it back on
        self.theta = K.VOICE_THETA + (5 if any(p.startswith(("urging", "overstating")) for p in check.problems)
                                      else -5)
        self.muted = True
        self.told.append({"step": fact.get("step"), "voice_theta": self.theta, "problems": check.problems})
        return out

    def unmute(self, operator_rank: int) -> None:
        """Only a human turns the voice back on (any logged-in operator)."""
        if operator_rank < 1:
            raise PermissionError("only an operator")
        self.muted, self.theta = False, K.VOICE_THETA
