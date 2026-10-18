"""The locked PSE textbook: the only thing any of our agents may give a
stranger (decided 18 Oct 2026).

Exactly one version is allowed: one Markdown file, UTF-8, NFC, LF line
endings, whose SHA-256 a human operator pins in SHARED_LIB after checking
Andrej Ristic's Ed25519 signature (`ssh-keygen -Y sign -n pse-textbook`).
Before anything leaves for a stranger it is hashed: equal to the pinned hash,
it passes; anything else is a leak. A stranger that sends us a "textbook"
whose hash is not the pinned one is an enemy.

This module is pure: hashing and the file's form. Checking the signature
calls ssh-keygen and lives in the shell (shell/lock.py).
"""
from __future__ import annotations

import hashlib
import unicodedata

NAMESPACE = "pse-textbook"
SIGNER = "andrej-ristic"
# The public half of Andrej's signing key is in triglav/keys/allowed_signers
# (fingerprint SHA256:2AE7b4r/6+XoObrRT41SlNSC+4YXdtvZG51Vf/PXml4). The
# private key never leaves his computer.


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def well_formed(data: bytes) -> list[str]:
    """What is wrong with the file's form (empty list: nothing). The form is
    fixed so the same text always gives the same bytes, and so the same hash."""
    problems = []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return ["not UTF-8"]
    if text.startswith("﻿"):
        problems.append("starts with a byte-order mark")
    if "\r" in text:
        problems.append("has CR line endings (LF only)")
    if unicodedata.normalize("NFC", text) != text:
        problems.append("not in Unicode NFC")
    if not text.endswith("\n"):
        problems.append("does not end with a newline")
    return problems
