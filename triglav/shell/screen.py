"""The screen: a local web page over SHARED_LIB (phase 4, decided 18 Oct 2026).

    triglav screen            # opens http://127.0.0.1:<port>/?t=<token> in the browser

It listens on 127.0.0.1 only, on a free port, and every request must carry a
random token made at start. It shows the semaphore, the agents with their
theta, the decisions, the inbox and the voice. It acts (release, mark read,
show a held part, voice on) only for the logged-in operator, after a
confirming click on the page.

The conversation tab: the human asks in their own words; the local model only
turns the question into one of a fixed set of queries; the answer is built from
SHARED_LIB's facts (and may be retold by the voice, which is checked). The
model never sees agents' messages. Anything that changes state is only
proposed, as a button.
"""
from __future__ import annotations

import json
import secrets
import statistics
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import parse_qs, urlparse

from ..core.voicetext import render

QUERIES = ("status", "enemies", "history", "held", "missions", "explain", "propose-release", "unknown")


def state(lib, operator: str | None) -> dict:
    """Everything the page shows, from SHARED_LIB's state and log."""
    lib.reload()
    reps = lib.store.entries("reports")
    last = reps[-1]["data"]["reports"] if reps else []
    peer: dict[str, list] = {}
    own: dict[str, float] = {}
    for r in last:
        own[r["observer"]] = r["observer_theta"]
        for who, v in r["peers"].items():
            peer.setdefault(who, []).append(v[0])
    s = lib.s
    names = sorted(set(s["kinds"]) | set(own))
    agents = []
    for n in names:
        theta = own.get(n)
        if theta is None and n in peer:
            theta = round(statistics.median(peer[n]), 2)
        status = ("enemy" if n in s["stopped"] else "physician" if n in s["quarantined"]
                  else "harvested" if n in s["harvested"] else "watched" if n in s["watched"]
                  else "kept-away" if n in s["separated"] else s["kinds"].get(n, "stranger"))
        agents.append({"name": n, "theta": theta, "status": status,
                       "mission": (s["missions"].get(n) or {}).get("mission", {}).get("text")})
    ok, why = lib.store.verify()
    inbox = [{"id": it["id"], "chain": it["chain_i"], "seen": it["seen"],
              "text": render(it["data"]) if it["kind"] != "proposal" else it["data"]["text"],
              "kind": it["kind"], "who": it["who"], "quarantine": it["data"].get("quarantine", []),
              "reading_open": it["kind"] == "reading"
              and lib.s["readings"].get(str(it["chain_i"]), {}).get("open", False)}
             for it in lib.store.inbox()][-50:]
    return {"installation": lib.installation, "operator": operator,
            "rank": lib.rank(operator) if operator in s["operators"] else None,
            "log_ok": ok, "log_why": why, "textbook": (s["textbook"] or {}).get("sha256"),
            "settings": lib.settings(), "agents": agents, "inbox": inbox,
            "readings_below": sum(s["readings_below"].values())}


class Interpreter:
    """Turns a question into one of the fixed queries. A local model when it is
    there (it sees only the question), a few plain rules otherwise."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "phi4-mini"):
        self.base_url, self.model = base_url, model

    def rules(self, q: str) -> dict:
        low = q.lower()
        for words, query in ((("release", "pusti", "lift", "skini"), "propose-release"),
                             (("enem", "neprijatelj", "stopped", "zaustavljen"), "enemies"),
                             (("held", "hidden", "zadrž", "skriven", "karantin"), "held"),
                             (("mission", "misij"), "missions"),
                             (("why", "explain", "zašto", "objasni"), "explain"),
                             (("history", "happened", "istorij", "desilo"), "history"),
                             (("status", "how are", "kako", "stanje"), "status")):
            if any(w in low for w in words):
                target = next((w for w in low.replace("?", " ").split() if "-" in w or w[-1:].isdigit()), None)
                return {"query": query, "target": target}
        return {"query": "unknown", "target": None}

    def __call__(self, q: str, names: list[str]) -> dict:
        schema = {"type": "object", "properties": {
            "query": {"type": "string", "enum": list(QUERIES)},
            "target": {"type": "string", "enum": names + ["none"]}}, "required": ["query", "target"]}
        prompt = ("Map the operator's question to one query. status: overall state. enemies: who is stopped. "
                  "history: recent decisions. held: hidden parts held. missions: agents' missions. "
                  "explain: why something happened to target. propose-release: the operator wants an enemy "
                  "or a unit in care released. unknown: anything else. Question: " + q)
        try:
            body = json.dumps({"model": self.model, "stream": False, "format": schema,
                               "options": {"temperature": 0},
                               "messages": [{"role": "user", "content": prompt}]}).encode()
            req = urllib.request.Request(self.base_url + "/api/chat", body, {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                out = json.loads(json.load(r)["message"]["content"])
            if out.get("query") in QUERIES:
                t = out.get("target")
                return {"query": out["query"], "target": t if t in names else None, "by": "model"}
        except (OSError, ValueError, KeyError):
            pass
        return {**self.rules(q), "by": "rules"}


def answer(lib, q: dict) -> dict:
    """The answer to a fixed query, from SHARED_LIB's facts only."""
    st = state(lib, None)
    who = q.get("target")
    kind = q["query"]
    if kind == "status":
        bad = [a for a in st["agents"] if a["status"] in ("enemy", "physician", "watched", "kept-away")]
        text = (f"Installation {st['installation']}. Log {'intact' if st['log_ok'] else 'BROKEN'}. "
                f"{len(st['agents'])} agents known; {len(bad)} with a decision on them. "
                f"Inbox: {sum(1 for i in st['inbox'] if not i['seen'])} unread.")
    elif kind == "enemies":
        e = lib.enemies()
        text = "; ".join(f"{k}: {v}" for k, v in sorted(e.items())) or "Nobody is stopped."
    elif kind == "history":
        text = " ".join(i["text"] for i in st["inbox"][-5:]) or "Nothing has happened yet."
    elif kind == "held":
        items = [i for i in st["inbox"] if i["quarantine"]]
        text = " ".join(i["text"] for i in items[-5:]) or "Nothing is held."
    elif kind == "missions":
        text = " ".join(f"{a['name']}: {a['mission']}." for a in st["agents"] if a["mission"]) or "No missions."
    elif kind == "explain" and who:
        items = [i for i in st["inbox"] if i["who"] == who]
        text = items[-1]["text"] if items else f"Nothing was decided about {who}."
    elif kind == "propose-release" and who:
        return {"text": f"Release {who}? Only an operator can, with the button.",
                "propose": {"action": "release", "who": who}}
    else:
        text = ("I can tell you the status, who is stopped, what happened recently, what is held, "
                "the missions, or why something happened to an agent.")
    return {"text": text}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _ok(self) -> bool:
        q = parse_qs(urlparse(self.path).query)
        t = self.headers.get("X-Triglav-Token") or (q.get("t") or [""])[0]
        return secrets.compare_digest(t, self.server.token)

    def _send(self, code: int, body: bytes, ctype: str = "application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/app.js":                 # the page's script: static, holds no data
            return self._send(200, resources.files("triglav.screen").joinpath("app.js").read_bytes(),
                              "text/javascript; charset=utf-8")
        if not self._ok():
            return self._send(403, b'{"error":"token"}')
        if path == "/":
            page = resources.files("triglav.screen").joinpath("index.html").read_bytes()
            return self._send(200, page, "text/html; charset=utf-8")
        if path == "/api/state":
            with self.server.lock:
                return self._send(200, json.dumps(state(self.server.lib, self.server.operator)).encode())
        return self._send(404, b'{"error":"not found"}')

    def do_POST(self):
        if not self._ok():
            return self._send(403, b'{"error":"token"}')
        n = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(n) or b"{}")
        lib, op = self.server.lib, self.server.operator
        path = urlparse(self.path).path
        with self.server.lock:
            try:
                if path == "/api/chat":
                    names = sorted(lib.s["kinds"])
                    q = self.server.interpreter(str(body.get("q", ""))[:500], names)
                    out = {**answer(lib, q), "query": q}
                elif path == "/api/act":
                    if op is None:
                        raise PermissionError("no operator is logged in (triglav operator login NAME)")
                    if body.get("confirm") is not True:
                        raise PermissionError("not confirmed")
                    act = body.get("action")
                    if act == "release":
                        out = {"done": lib.release(op, str(body["who"]))}
                    elif act == "read":
                        lib.store.mark_seen(int(body["id"]))
                        lib.store.commit()
                        out = {"done": True}
                    elif act == "held":
                        out = lib.held(str(body["q"]))
                    elif act == "reading":
                        out = {"done": lib.decide_reading(op, int(body["id"]), bool(body["verdict"]))}
                    elif act == "voice-on":
                        lib.set_setting(op, "voice_muted", False)
                        out = {"done": True}
                    else:
                        raise ValueError(f"unknown action {act!r}")
                else:
                    return self._send(404, b'{"error":"not found"}')
                return self._send(200, json.dumps(out).encode())
            except (PermissionError, ValueError, KeyError) as e:
                return self._send(400, json.dumps({"error": str(e)}).encode())


def make_screen(lib, operator: str | None, interpreter=None, port: int = 0):
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    import threading
    srv.lib, srv.operator, srv.token, srv.lock = lib, operator, secrets.token_urlsafe(24), threading.Lock()
    srv.interpreter = interpreter or Interpreter()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/?t={srv.token}"
