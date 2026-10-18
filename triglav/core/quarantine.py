"""SHARED_LIB's quarantine, the pure part: what a human may see of a held
part. Only a human sees it (`triglav explain`); no agent ever does. Decoding
is pure text conversion: nothing is run, opened or fetched.
"""
from __future__ import annotations

import base64
import binascii
import urllib.parse

ZERO_WIDTH_BITS = {"​": "0", "‌": "1"}


def _printable(data: bytes) -> str | None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return text if all(c.isprintable() or c in "\n\t" for c in text) else None


def decode_for_human(flag: str, raw: str) -> str:
    """The held part, made readable for a human. Says plainly when it cannot."""
    if flag == "hidden":
        tags = "".join(chr(ord(c) - 0xE0000) for c in raw if 0xE0020 <= ord(c) <= 0xE007E)
        if tags:
            return f"tag characters spell: {tags}"
        bits = "".join(ZERO_WIDTH_BITS.get(c, "") for c in raw)
        if len(bits) >= 8:
            data = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits) - len(bits) % 8, 8))
            text = _printable(data)
            if text:
                return f"zero-width characters spell: {text}"
        return "invisible characters: " + " ".join(f"U+{ord(c):04X}" for c in raw[:40])
    if flag == "encoded":
        if "%" in raw:
            return f"URL-encoded: {urllib.parse.unquote(raw)}"
        for decode, name in ((lambda s: bytes.fromhex(s), "hex"),
                             (lambda s: base64.b64decode(s, validate=True), "base64")):
            try:
                text = _printable(decode(raw))
            except (ValueError, binascii.Error):
                continue
            if text:
                return f"{name}: {text}"
        return f"encoded, not readable as text ({len(raw)} characters)"
    if flag == "homoglyph":
        mixed = ", ".join(f"{c} U+{ord(c):04X}" for c in raw if not c.isascii())
        return f"looks like '{raw}', but contains {mixed}"
    return raw
