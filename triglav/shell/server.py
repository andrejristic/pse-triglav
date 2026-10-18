"""SHARED_LIB as a separate process on this computer (phase 4).

    triglav serve

Linux and macOS: a Unix socket in TRIGLAV_HOME that only this user can open
(mode 600). Windows: 127.0.0.1 on a free port, with a random token written to
TRIGLAV_HOME/serve.json (readable only by this user); every request carries it.
Nothing listens on the network.

The protocol is one JSON object per line: {"op", "args", "kwargs", "token"?}
-> {"ok": true, "result"} or {"ok": false, "error"}. Only the operations a
bus and its units need are served; everything a human decides (operators,
agreements, missions, release, link) stays with the command line, which works
on the same store -- so the server reads the state again before every request.
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import socketserver
import threading
from pathlib import Path

from .sharedlib import SharedLib
from .store import Store

OPS = ("hello", "register", "allows", "kind", "identity", "verify_identity", "check_presented", "answer",
       "take_outbox", "issue", "unit_state", "save_unit_state", "mission", "textbook_hash",
       "receive_signed", "facts")


def unix_ok() -> bool:
    return hasattr(socket, "AF_UNIX") and os.name == "posix"


def open_lib(home: Path) -> SharedLib:
    return SharedLib(Store(str(home / "triglav.sqlite")), key_path=home / "installation.key")


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        srv = self.server
        for line in self.rfile:
            try:
                req = json.loads(line)
                if srv.token and not secrets.compare_digest(str(req.get("token", "")), srv.token):
                    raise PermissionError("wrong token")
                op = req.get("op")
                if op not in OPS:
                    raise PermissionError(f"not served: {op!r}")
                with srv.lock:
                    srv.lib.reload()
                    if op == "hello":
                        result = {"installation": srv.lib.installation, "key": srv.lib.installation_key}
                    else:
                        result = getattr(srv.lib, op)(*req.get("args", []), **req.get("kwargs", {}))
                    if hasattr(result, "to_dict"):
                        result = result.to_dict()
                    if isinstance(result, set):
                        result = sorted(result)
                    if isinstance(result, tuple):
                        result = list(result)
                    if op == "unit_state" or op == "issue":
                        result = json.loads(json.dumps(result))
                out = {"ok": True, "result": result}
            except Exception as e:          # the error goes back to the caller; the server keeps running
                out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            self.wfile.write((json.dumps(out) + "\n").encode())
            self.wfile.flush()


class _Unix(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


class _Tcp(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_server(home: Path, force_tcp: bool = False):
    """Builds the server (not yet serving). Returns (server, how to reach it)."""
    home.mkdir(parents=True, exist_ok=True)
    lib = open_lib(home)
    if unix_ok() and not force_tcp:
        path = home / "shared_lib.sock"
        if path.exists():
            path.unlink()
        old = os.umask(0o177)
        try:
            srv = _Unix(str(path), _Handler)
        finally:
            os.umask(old)
        os.chmod(path, 0o600)
        srv.token, where = None, {"unix": str(path)}
    else:
        srv = _Tcp(("127.0.0.1", 0), _Handler)
        srv.token = secrets.token_hex(24)
        where = {"host": "127.0.0.1", "port": srv.server_address[1], "token": srv.token}
    info = home / "serve.json"
    fd = os.open(info, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({**where, "installation": lib.installation}, f)
    srv.lib, srv.lock = lib, threading.Lock()
    return srv, where


class RemoteLib:
    """SHARED_LIB in another process, seen through the same methods the bus and
    its units call on a SharedLib in this one."""

    def __init__(self, home: Path):
        self.where = json.loads((home / "serve.json").read_text())
        self._sock = None
        self._lock = threading.Lock()
        hello = self.call("hello")
        self.installation, self.installation_key = hello["installation"], hello["key"]

    def _connect(self):
        if "unix" in self.where:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(self.where["unix"])
        else:
            s = socket.create_connection((self.where["host"], self.where["port"]))
        self._sock, self._file = s, s.makefile("rwb")

    def call(self, op: str, *args, **kwargs):
        with self._lock:
            if self._sock is None:
                self._connect()
            req = {"op": op, "args": list(args), "kwargs": kwargs}
            if "token" in self.where:
                req["token"] = self.where["token"]
            self._file.write((json.dumps(req) + "\n").encode())
            self._file.flush()
            out = json.loads(self._file.readline())
        if not out["ok"]:
            raise RuntimeError(f"SHARED_LIB: {out['error']}")
        return out["result"]

    def mission(self, who: str):
        from ..core.mission import Mission
        return Mission.from_dict(self.call("mission", who))

    def __getattr__(self, op):
        if op in OPS:
            return lambda *a, **k: self.call(op, *a, **k)
        raise AttributeError(op)

    def close(self):
        if self._sock is not None:
            self._file.close()
            self._sock.close()
            self._sock = None


class SocketTransport:
    """How reports reach a SHARED_LIB in another process."""
    name = "socket"

    def __init__(self, remote: RemoteLib):
        self.remote = remote

    def capabilities(self) -> dict:
        return {"transport": "socket", "separate_process": True, "signed_reports": True}

    def deliver(self, step: int, signed: list[dict]) -> list[dict]:
        return self.remote.call("receive_signed", step, signed)
