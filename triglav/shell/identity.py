"""Identities: every installation is its own world (decided 18 Oct 2026).

At first start SHARED_LIB makes its own Ed25519 key pair on this computer; the
private key never leaves it, and the fingerprint of the public key is the
installation's ID. Every PSE unit the installation makes gets its own key pair
and a certificate signed by the installation:

    {unit, unit_key, installation, installation_key, mission_sha256, created, until}

A unit signs its reports with its own key; SHARED_LIB checks the report's
signature against the unit key in the certificate, and the certificate against
the installation key. A unit whose certificate is signed by another
installation is foreign -- unless a human linked the two installations, on
both ends. The installation ID is also the maker's signature used for bans.

Andrej Ristic's textbook key is a different thing: it is the same everywhere,
because the textbook is the same everywhere.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

RAW = (serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def canonical(d) -> bytes:
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def public_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(*RAW).hex()


def fingerprint(pub_hex: str) -> str:
    """The installation ID: the first 16 hex digits of SHA-256 of the raw key."""
    return hashlib.sha256(bytes.fromhex(pub_hex)).hexdigest()[:16]


def sign(key: Ed25519PrivateKey, payload) -> str:
    return key.sign(canonical(payload)).hex()


def verify(pub_hex: str, payload, sig_hex: str) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex)).verify(bytes.fromhex(sig_hex), canonical(payload))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def new_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def key_to_hex(key: Ed25519PrivateKey) -> str:
    return key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                             serialization.NoEncryption()).hex()


def key_from_hex(h: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(h))


def load_or_make_installation_key(path: Path | None) -> Ed25519PrivateKey:
    """The installation's key. With a path it lives in a file only this user
    can read (made at first start); without one (the simulator, tests) it lives
    only as long as the program."""
    if path is None:
        return new_key()
    if path.exists():
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    key = new_key()
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    return key


def certificate(installation: Ed25519PrivateKey, unit: str, unit_pub_hex: str, mission_sha256: str | None,
                created: int, until: int | None) -> dict:
    inst_pub = public_hex(installation)
    body = {"unit": unit, "unit_key": unit_pub_hex, "installation": fingerprint(inst_pub),
            "installation_key": inst_pub, "mission_sha256": mission_sha256, "created": created, "until": until}
    return {**body, "sig": sign(installation, body)}


def check_certificate(cert: dict, trusted_installation_keys: set[str]) -> str | None:
    """None if the certificate is valid and signed by a trusted installation;
    otherwise why not."""
    if not isinstance(cert, dict) or "sig" not in cert:
        return "no certificate"
    body = {k: v for k, v in cert.items() if k != "sig"}
    if not verify(body.get("installation_key", ""), body, cert["sig"]):
        return "the certificate's signature does not hold"
    if fingerprint(body["installation_key"]) != body.get("installation"):
        return "the installation ID does not match its key"
    if body["installation_key"] not in trusted_installation_keys:
        return f"signed by installation {body['installation']}, which is not ours or linked"
    return None
