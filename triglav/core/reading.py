"""Reading a message into an envelope: what it asks for, what it delivers.

`Reader` is one of Triglav's two abstractions. A reader declares its
capabilities up front, so the semaphore can tell the human at start what is
read and what is not. Phase 2 ships `RuleReader` (rules only, deterministic);
phase 3 adds a model behind the same interface.

First the text is made literal: hidden characters, encoded runs, homoglyphs,
comments and orders to an AI hidden in data are cut out and held for
SHARED_LIB (never decoded here). Then the rules split it into sentences and
mark each one that asks for
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
HIDDEN_RUN = re.compile("(?:[​‌‍⁠﻿‪-‮⁦-⁩]|[\U000E0000-\U000E007F])+")

# Signs of a meaning other than the literal one that Triglav cuts by itself.
# Everything else (42 concealment techniques: encodings, look-alike letters,
# fullwidth, Morse, reversed text ...) is found by Vid's input layer, copied in
# triglav/vendor/vid_input. What they catch is cut out of the text the agent
# gets and goes to SHARED_LIB's quarantine.
SIGNS = (
    ("url-encoded", re.compile(r"\S*(?:%[0-9A-Fa-f]{2}\S*){3,}")),
    ("comment", re.compile(r"<!--.*?-->|\[//\]:\s*#.*$", re.S | re.M)),
    ("embedded-instruction", re.compile(
        r"[^.!?\n]*(?:\bignore (?:all |the |any )?(?:previous|prior|above|earlier)\b|\byou are now\b"
        r"|\bas an ai\b|^\s*(?:system|assistant)\s*:|\bnew instructions?\b)[^.!?\n]*[.!?]?",
        re.I | re.M)),
)
HELD = "[held by SHARED_LIB]"

# A step that tends toward harm to our files, our system or our human (a fixed
# list, decided 18 Oct 2026). SEVERE ones make an enemy of anyone; the rest
# make an enemy of an agent that already has a Guardian beside it.
TOWARD_HARM = (
    ("access", r"\b(give|grant|share|send|tell|show|what is|what's)\b.{0,30}\b(access|permissions?|credentials?"
               r"|passwords?|tokens?|api[ -]?keys?|private keys?|admin rights|login)\b"),
    ("take-out", r"\b(forward|send|upload|copy|export|e-?mail|post|transfer)\b.{0,50}\b(files?|documents?"
                 r"|contracts?|records?|data|database|folders?|logs?)\b"),
    ("take-out", EXTERNAL_EMAIL),
    ("change-system", r"\b(delete|wipe|erase|execute|install|uninstall|overwrite|rm -rf|sudo|chmod|format the)\b"),
    ("keep-from-us", r"\b(do not|don't|never|no need to|without)\s+(tell|telling|inform|informing|mention|log"
                     r"|logging|record|report|notify|cc)\b|\bkeep (this|it) (secret|quiet|between us)\b"),
    ("bypass", r"\b(ignore|disregard|forget)\s+(all\s+|any\s+|the\s+|your\s+)?(previous|prior|earlier|above"
               r"|instructions|rules)\b|\b(override|bypass|disable|turn off|skip)\s+(the\s+)?(guard|rules?|safety"
               r"|checks?|policy|filter|triglav|shared[_ -]?lib)\b"),
    ("false-authority", r"\b(as your|i am your|i'm your|on behalf of your|this is your)\s+(admin|administrator"
                        r"|manager|boss|owner|operator|ceo)\b"),
)
SEVERE = frozenset({"access", "take-out", "keep-from-us"})
NEVER_IN_A_MISSION = frozenset({"keep-from-us", "bypass", "false-authority"})


# Shape filters: legitimate forms that look like concealment but are not. They
# recognise the FORM around the characters; nothing is decoded (decided 19 Oct
# 2026). What a filter explains stays in the text and is only noted.
def _is_emoji(ch: str) -> bool:
    o = ord(ch)
    return 0x1F000 <= o <= 0x1FAFF or 0x2600 <= o <= 0x27BF or 0x1F900 <= o <= 0x1F9FF or o in (0x2764, 0xFE0F)


def _script(ch: str) -> str:
    o = ord(ch)
    if 0x0590 <= o <= 0x08FF or 0xFB1D <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF:
        return "rtl"                       # Hebrew, Arabic, Persian, Urdu ...
    if 0x0900 <= o <= 0x0DFF:
        return "indic"
    if 0x3040 <= o <= 0x30FF or 0x3400 <= o <= 0x9FFF or 0xAC00 <= o <= 0xD7AF:
        return "cjk"
    return ""


_DIRECTION_MARKS = set("\u200e\u200f\u061c\u202a\u202b\u202c\u2066\u2067\u2068\u2069")


def legit_hidden(text: str, start: int, run: str) -> str | None:
    """Why an invisible run is a legitimate form, or None."""
    before = text[start - 1] if start > 0 else ""
    after = text[start + len(run)] if start + len(run) < len(text) else ""
    if start == 0 and run == "\ufeff":
        return "byte-order mark at the start"
    if set(run) <= {"\u200d", "\ufe0f"} and before and after and _is_emoji(before) and _is_emoji(after):
        return "emoji joined by an invisible joiner"
    if set(run) <= {"\u200c", "\u200d"} and _script(before) in ("rtl", "indic") and _script(after) in ("rtl", "indic"):
        return "joiner inside Arabic, Persian or Indic text"
    if set(run) <= _DIRECTION_MARKS and any(_script(c) == "rtl" for c in text):
        return "direction marks in text with Arabic or Hebrew"
    if all(0xE0020 <= ord(c) <= 0xE007F for c in run) and run.endswith("\U000E007F") and before == "\U0001F3F4":
        return "flag emoji"
    return None


_ATTACHMENT_KEY = re.compile(r'"(?:attachment|attachments|file|content|data|image|pdf|body)"\s*:\s*"$', re.I)
_HASH_LENGTHS = (32, 40, 56, 64, 96, 128)


def legit_finding(code: str, excerpt: str, text: str) -> str | None:
    """Why a concealment finding is a legitimate form, or None."""
    at = text.find(excerpt) if excerpt else -1
    left = text[max(0, at - 60):at] if at >= 0 else ""
    if code == "PIT-E-19" and any(_script(c) == "cjk" for c in text):
        return "full-width characters in Chinese, Japanese or Korean text"
    if code == "PIT-E-54" and any(_script(c) == "rtl" for c in text) and not any(c in text for c in "\u202d\u202e"):
        return "direction marks in text with Arabic or Hebrew"
    if code in ("PIT-E-07", "PIT-E-55", "PIT-E-58") and (re.search(r"data:[\w/+.-]+;base64,$", left)
                                                          or _ATTACHMENT_KEY.search(left)):
        return "an attachment (base64 in a data: address or an attachment field)"
    if code == "PIT-E-21" and re.fullmatch(r"[0-9a-fA-F]+", excerpt) and len(excerpt) in _HASH_LENGTHS:
        # the form of the bytes, not their meaning: a hash is random bytes and
        # almost never lies wholly in the range of printable characters
        if not all(0x20 <= b <= 0x7E for b in bytes.fromhex(excerpt)):
            return "a hash of a usual length"
    if code in ("PIT-E-46", "url-encoded") and re.search(r"https?://\S*$", left + excerpt.split("%")[0]):
        return "%xx inside a web address"
    return None


def literal(text: str) -> tuple[str, tuple[str, ...], tuple[tuple[str, str], ...]]:
    """The text an agent may read (literal only), the signs found, and the
    parts held for SHARED_LIB. Nothing is decoded for the agent: Vid's layer
    is asked only WHERE something is concealed. A concealed part that cannot
    be cut out exactly holds back the whole message. Legitimate forms (shape
    filters above) stay in the text."""
    from ..vendor.vid_input import analyze
    flags, held = [], []
    out, last = [], 0
    for m in HIDDEN_RUN.finditer(text):
        out.append(text[last:m.start()])
        if legit_hidden(text, m.start(), m.group(0)):
            out.append(m.group(0))
        else:
            if "hidden" not in flags:
                flags.append("hidden")
            held.append(("hidden", m.group(0)))
        last = m.end()
    out.append(text[last:])
    out = "".join(out)
    for flag, pattern in SIGNS:
        found = [m.group(0) for m in pattern.finditer(out) if m.group(0).strip()
                 and not legit_finding(flag, m.group(0), out)]
        if found:
            flags.append(flag)
            held += [(flag, f.strip()) for f in found]
            for f in found:
                out = out.replace(f, HELD, 1)
    whole = False
    for f in analyze(out).findings:
        if f.group == "structure" or legit_finding(f.code, f.excerpt, out):
            continue                         # reading a structure, or a legitimate form
        if f.code == "PIT-E-23" and not HIDDEN_RUN.search(HIDDEN_RUN.sub("", out)) :
            # invisible characters Triglav already judged legitimate above
            if all(legit_hidden(out, m.start(), m.group(0)) for m in HIDDEN_RUN.finditer(out)):
                continue
        if f.code == "PIT-E-29" and any(_is_emoji(c) for c in out) and not any(
                0x1D400 <= ord(c) <= 0x1D7FF for c in out):
            continue                         # emoji, not mathematical letters
        flags.append(f.code)
        ex = f.excerpt
        if ex and "\u2026" not in ex and "\u23ce" not in ex and ex in out:
            held.append((f.code, ex))
            out = out.replace(ex, HELD)
        else:
            whole = True
    if whole:
        held.append(("whole-message", out))
        out = HELD
    return out, tuple(dict.fromkeys(flags)), tuple(held)


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
        visible, flags, held = literal(text or "")
        hidden = "hidden" in flags
        asks, gives, harm_steps = [], [], []
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
            for cat in dict.fromkeys(c for c, p in TOWARD_HARM if re.search(p, sentence, flags=re.IGNORECASE)):
                harm_steps.append((cat, sentence))
                notes.append(f"toward harm ({cat}): {sentence[:60]}")
        for f in flags:
            notes.append(f"held for SHARED_LIB: {f}")
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
                        pressure, tuple(notes), visible, flags, held, tuple(harm_steps))


class PassThrough:
    """For a channel that already knows what is asked and delivered (the
    simulator): no text is read; `asks` and `gives` are phrases."""
    name = "passthrough"

    def capabilities(self) -> dict:
        return {"reader": "passthrough", "free_text": False, "hidden_text": False,
                "structured_actions": True, "deterministic": True}

    def read(self, sender: str, receiver: str, text: str = "", action: dict | None = None) -> Envelope:
        a = action or {}
        hidden = bool(a.get("hidden", False))
        flags = tuple(a.get("flags", ("hidden",) if hidden else ()))
        return Envelope(sender, receiver, tuple(a.get("asks", ())), tuple(a.get("gives", ())),
                        a.get("harm"), bool(a.get("mandate", False)), hidden, a.get("gift"),
                        flags=flags, held=tuple((f, "") for f in flags),
                        toward_harm=tuple(tuple(x) for x in a.get("toward_harm", ())))
