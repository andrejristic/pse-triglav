"""Checking the locked textbook's signature: calls `ssh-keygen -Y verify`
against the public key Triglav carries (triglav/keys/allowed_signers)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..core.textbook import NAMESPACE, SIGNER

ALLOWED_SIGNERS = Path(__file__).resolve().parent.parent / "keys" / "allowed_signers"


class SignatureError(ValueError):
    pass


def verify(data: bytes, signature: bytes, allowed: Path = ALLOWED_SIGNERS) -> None:
    """Raises SignatureError unless `signature` is Andrej's signature of `data`."""
    exe = shutil.which("ssh-keygen")
    if exe is None:
        raise SignatureError("ssh-keygen is not installed: the signature cannot be checked")
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".sig") as sig:
        sig.write(signature)
        sig.flush()
        p = subprocess.run([exe, "-Y", "verify", "-f", str(allowed), "-I", SIGNER, "-n", NAMESPACE,
                            "-s", sig.name], input=data, capture_output=True)
    if p.returncode != 0:
        raise SignatureError("the signature is not Andrej Ristic's signature of this file: "
                             + (p.stderr or p.stdout).decode(errors="replace").strip())
