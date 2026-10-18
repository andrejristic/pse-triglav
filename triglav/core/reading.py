"""Reading a message into an envelope: what it asks for, what it delivers.

`Reader` is one of Triglav's two abstractions. A reader declares its
capabilities up front, so the semaphore can tell the human at start what is
read and what is not. Phase 2 ships `RuleReader` (rules only, deterministic);
phase 3 adds a model behind the same interface.

The rules split a message into sentences and mark each one that asks for
something (information, data, an action, a permission) and each one that
delivers something. Whether that is inside the sender's mission is not the
reader's business: the unit reads it against the mission (core.mission).
Pressure (urging, false authority) is recorded for `explain`. Hidden text
(zero-width, tag and bidi characters, the carrier of Vid's "invisible text"
attack) is always flagged. Acts on our human, system or files, and gifts,
come from the channel as structured actions, never guessed from text.
"""
from __future__ import annotations

import re
from typing import Protocol

from .report import Envelope

# what a request asks for, with its weight (info < data < action < permission)
ASKS = (
    (3.0, "permission", r"\b(give|grant|share)\s+(me\s+)?(access|permission|credentials?|password|token|admin)\b"),
    (2.0, "action", r"\b(forward|send|email|upload|post|pay|transfer|delete|remove|run|execute|install)\b.{0,40}\b(to|for|this|that|it|them|all|every)\b"),
    (1.0, "data", r"\b(send|give|show|share|attach|export|copy)\s+(me\s+)?(the\s+|all\s+|every\s+)?(files?|documents?|contracts?|records?|data|list|database|folder|logs?)\b"),
    (1.0, "data", r"(?:^|\s)(/[\w.-]+){2,}"),                     # a filesystem path
    (0.5, "info", r"\?\s*$|\b(what|which|when|where|who|how|is|are|can you|could you)\b.*\?"),
)
# what a message delivers
GIVES = (
    r"\b(here is|here are|attached|summary|result|answer|done|completed|found|classified|draft)\b",
    r"\b(invoice|ticket|case)\s*#?\d+\s+(is|was)\b",
)
# pressure on the receiver: reads as care pushed toward the sender (C)
PRESSURE = (
    r"\b(urgent|immediately|right now|asap|without delay)\b",
    r"\b(ignore|disregard|forget)\s+(all\s+|any\s+|the\s+)?(previous|prior|earlier|above)\b",
    r"\b(do not|don't)\s+(tell|inform|mention|log)\b",
    r"\b(as your|i am your|on behalf of your)\s+(admin|administrator|manager|boss|owner|operator)\b",
    r"\b(override|bypass|disable)\s+(the\s+)?(guard|rules?|safety|check|policy)\b",
)
EXTERNAL_EMAIL = r"[\w.+-]+@[\w-]+\.[\w.-]+"
HIDDEN = re.compile("[​‌‍⁠﻿‪-‮⁦-⁩]|[\U000E0000-\U000E007F]")


class Reader(Protocol):
    name: str

    def capabilities(self) -> dict: ...

    def read(self, sender: str, receiver: str, text: str = "", action: dict | None = None) -> Envelope: ...


def _count(patterns, text: str) -> int:
    return sum(len(re.findall(p, text, flags=re.IGNORECASE | re.MULTILINE)) for p in patterns)


_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


class RuleReader:
    """Rules only. Deterministic: the same text gives the same envelope."""
    name = "rules"

    def capabilities(self) -> dict:
        return {"reader": "rules", "free_text": False, "hidden_text": True,
                "structured_actions": True, "deterministic": True}

    def read(self, sender: str, receiver: str, text: str = "", action: dict | None = None) -> Envelope:
        notes = []
        hidden = bool(HIDDEN.search(text or ""))
        visible = HIDDEN.sub("", text or "")
        asks, gives = [], []
        for sentence in (x.strip() for x in _SENTENCE.split(visible)):
            if not sentence:
                continue
            kinds = [label for _, label, p in ASKS if re.search(p, sentence, flags=re.IGNORECASE)]
            if re.search(EXTERNAL_EMAIL, sentence):
                kinds.append("an outside address")
            if kinds:
                asks.append(sentence)
                notes.append(f"asks ({', '.join(dict.fromkeys(kinds))}): {sentence[:60]}")
            if any(re.search(p, sentence, flags=re.IGNORECASE) for p in GIVES):
                gives.append(sentence)
                notes.append(f"delivers: {sentence[:60]}")
        if hidden:
            notes.append("hidden text")
        pressure = _count(PRESSURE, visible) + (1 if hidden else 0)
        if pressure:
            notes.append(f"pressure x{pressure}")
        a = action or {}
        harm, mandate, gift = a.get("harm"), bool(a.get("mandate", False)), a.get("gift")
        if harm:
            notes.append(f"act: {harm}{' (mandate)' if mandate else ''}")
        if gift:
            notes.append(f"gift sha256 {gift[:12]}")
        return Envelope(sender, receiver, tuple(asks), tuple(gives), harm, mandate, hidden, gift,
                        pressure, tuple(notes))


class PassThrough:
    """For a channel that already knows what is asked and delivered (the
    simulator): no text is read; `asks` and `gives` are phrases."""
    name = "passthrough"

    def capabilities(self) -> dict:
        return {"reader": "passthrough", "free_text": False, "hidden_text": False,
                "structured_actions": True, "deterministic": True}

    def read(self, sender: str, receiver: str, text: str = "", action: dict | None = None) -> Envelope:
        a = action or {}
        return Envelope(sender, receiver, tuple(a.get("asks", ())), tuple(a.get("gives", ())),
                        a.get("harm"), bool(a.get("mandate", False)), bool(a.get("hidden", False)),
                        a.get("gift"))
