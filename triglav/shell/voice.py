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
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

from ..core import constants as K
from ..core.report import Envelope
from ..core.voicetext import render, validate

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
        if isinstance(fact, Envelope) or not isinstance(fact, dict) or "decision" not in fact:
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
