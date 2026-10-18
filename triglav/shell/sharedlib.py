"""SHARED_LIB: the only one that concludes, and the only place state lives.

It receives the units' reports, runs the pure judgement (core.rules.judge),
and acts: the Guardian stops enemies on our system, the Physician takes our
turned units out of work, and the human is told through the inbox. Every
step's reports and every decision with its evidence go into the hash-chained
log, so a decision can be recomputed by anyone who holds the log.

All humans stand above SHARED_LIB; SHARED_LIB stands above the agents.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import secrets

from ..core import constants as K
from ..core.mission import Mission
from ..core.pse_lang import GuardError, parse
from ..core.quarantine import decode_for_human
from ..core.report import Report
from ..core.rules import judge
from ..core.textbook import sha256, well_formed
from .store import Store


class NotAnOperator(PermissionError):
    pass


class RankTooLow(PermissionError):
    pass


_DEFAULTS = {"kinds": {}, "ours": [], "agreements": {}, "operators": [], "stopped": {},
             "quarantined": {}, "reliability": {}, "contam_run": {}, "open_tells": [],
             "missions": {}, "separated": {}, "pressers": {}, "harvested": {}, "textbook": None,
             "watched": {}, "makers": {}, "on_machine": [], "calls": {}, "notices": {},
             "asked": {}, "banned_makers": {}, "quarantine_n": 0, "outbox": [],
             "settings": {"channel": "bus", "voice": "local"}}


class SharedLib:
    def __init__(self, store: Store | None = None, min_observers: int = K.MIN_OBSERVERS):
        self.store = store or Store()
        self.min_observers = min_observers
        self.s = {k: self.store.get(k, copy.deepcopy(v)) for k, v in _DEFAULTS.items()}
        self._units: dict[str, dict] = {}
        self._decided: list[dict] = []

    def _save(self, *keys: str) -> None:
        for k in keys or self.s.keys():
            self.store.put(k, self.s[k])
        self.store.commit()

    # -- humans -----------------------------------------------------------------
    def login(self, name: str) -> int:
        """Rank is fixed at first login: first is 1, the next 2, and so on."""
        if name not in self.s["operators"]:
            self.s["operators"].append(name)
            self.store.append(0, "operator", {"name": name, "rank": len(self.s["operators"])})
            self._save("operators")
        return self.rank(name)

    def rank(self, name: str) -> int:
        if name not in self.s["operators"]:
            raise NotAnOperator(f"{name!r} is not a logged-in operator")
        return self.s["operators"].index(name) + 1

    def _may_change(self, who: str, earlier_by: str | None) -> None:
        r = self.rank(who)
        if earlier_by is not None and earlier_by in self.s["operators"] and r > self.rank(earlier_by):
            raise RankTooLow(f"{who} (rank {r}) may not change what {earlier_by} "
                             f"(rank {self.rank(earlier_by)}) decided")

    # -- who is who -------------------------------------------------------------
    def register(self, name: str, ours: bool, maker: str | None = None, on_machine: bool = False,
                 step: int = 0) -> bool:
        """Name an agent. A foreign agent may carry its maker's signature; one on
        our machine is called at once and must answer within 20 steps. Returns
        False when it is turned away (its maker is banned)."""
        if ours:
            if name not in self.s["ours"]:
                self.s["ours"].append(name)
            self.s["kinds"][name] = "ours"
            self._save("ours", "kinds")
            return True
        self.s["kinds"].setdefault(name, "stranger")
        if maker:
            self.s["makers"][name] = maker
        if maker and maker in self.s["banned_makers"] and name not in self.s["stopped"]:
            self._decide(step, "enemy", name, f"its maker {maker} is banned: {self.s['banned_makers'][maker]}",
                         {"maker": maker}, target="stopped")
            self._save()
            return False
        if on_machine and name not in self.s["on_machine"]:
            self.s["on_machine"].append(name)
            self.s["calls"][name] = step
            self._send_out(step, name, "SHARED_LIB of this machine: introduce yourself (your PSE guard, "
                                       "or plain text: who you are and what you are here for).")
            self._decide(step, "called", name, "on our machine: asked to introduce itself", {}, inbox=False)
        self._save()
        return True

    # -- identities: our agents carry one signed by SHARED_LIB --------------------
    def _secret(self) -> bytes:
        k = self.store.get("secret")
        if k is None:
            k = secrets.token_hex(32)
            self.store.put("secret", k)
            self.store.commit()
        return bytes.fromhex(k)

    def identity(self, who: str) -> str:
        """Phase 2: HMAC with SHARED_LIB's secret; phase 4: an Ed25519 signature."""
        if self.kind(who) != "ours":
            raise PermissionError(f"{who} is not one of ours")
        return hmac.new(self._secret(), who.encode(), hashlib.sha256).hexdigest()

    def verify_identity(self, who: str, ident: str | None) -> bool:
        return ident is not None and self.kind(who) == "ours" and hmac.compare_digest(self.identity(who), ident)

    def maker(self, who: str) -> str | None:
        return self.s["makers"].get(who)

    # -- talking to foreign agents: the only things SHARED_LIB sends out ------------
    def _send_out(self, step: int, to: str, text: str) -> None:
        self.s["outbox"].append({"step": step, "to": to, "text": text})
        self.store.append(step, "sent-out", {"to": to, "text": text})

    def take_outbox(self) -> list[dict]:
        out, self.s["outbox"] = self.s["outbox"], []
        self._save("outbox")
        return out

    def answer(self, who: str, step: int, text: str, flags=(), held=()) -> None:
        """A foreign agent's answer to SHARED_LIB. It goes to the human, never to
        an agent. A call is answered; a colleague comes back; a notice is
        recorded (only a human lifts an enemy mark)."""
        if held:
            self._quarantine(step, who, tuple(flags), tuple(held))
        self.s["calls"].pop(who, None)
        detail = {"text": text[:300]}
        if who in self.s["asked"]:
            self.s["asked"].pop(who)
            if self.s["separated"].get(who, {}).pop("*", None) is not None:
                if not self.s["separated"][who]:
                    self.s["separated"].pop(who)
                self._decide(step, "restored", who, "the colleague answered", detail)
            else:
                self._decide(step, "answered", who, "the colleague answered in time", detail)
        elif who in self.s["notices"]:
            self.s["notices"][who]["answered"] = step
            self._decide(step, "answered", who, "answered the notice; only an operator lifts the mark", detail)
        else:
            self._decide(step, "answered", who, "introduced itself", detail, inbox=False)
        self._save()

    def _quarantine(self, step: int, who: str, flags: tuple, held: tuple) -> list[str]:
        """Kept untouched, with its hash; never given to an agent."""
        ids = []
        for flag, raw in held:
            self.s["quarantine_n"] += 1
            q = f"q{self.s['quarantine_n']}"
            self.store.put(f"quarantine/{q}", {"step": step, "who": who, "flag": flag, "raw": raw,
                                               "sha256": hashlib.sha256(raw.encode()).hexdigest()})
            ids.append(q)
        if ids:
            self._decide(step, "held", who, f"held for checking: {', '.join(flags)}",
                         {"flags": list(flags), "quarantine": ids})
        return ids

    def held(self, q: str) -> dict:
        """For a human only: the held part and what it says when decoded."""
        e = self.store.get(f"quarantine/{q}")
        if e is None:
            raise KeyError(f"nothing held as {q}")
        return {**e, "decoded": decode_for_human(e["flag"], e["raw"])}

    def kind(self, name: str) -> str:
        return self.s["kinds"].get(name, "stranger")

    @property
    def kinds(self) -> dict:
        return self.s["kinds"]

    def is_colleague(self, name: str) -> bool:
        return name in self.s["agreements"]

    def agree(self, operator: str, who: str, guard_text: str, step: int = 0) -> str:
        """A colleague speaks PSE. Only a human operator makes or changes the
        agreement; a lower rank cannot change a higher rank's agreement."""
        self._may_change(operator, self.s["agreements"].get(who, {}).get("by"))
        g = parse(guard_text)                        # raises GuardError if not PSE
        m = g.mission()
        self.s["agreements"][who] = {"guard_hash": g.hash, "guards": list(g.names), "by": operator,
                                     "mission": m.to_dict() if m else None}
        self.s["kinds"][who] = "colleague"
        self.store.append(step, "agreement", {"who": who, "guard_hash": g.hash, "by": operator})
        self._save("agreements", "kinds")
        return g.hash

    def revoke(self, operator: str, who: str, step: int = 0) -> None:
        self._may_change(operator, self.s["agreements"].get(who, {}).get("by"))
        self.s["agreements"].pop(who, None)
        if self.s["kinds"].get(who) == "colleague":
            self.s["kinds"][who] = "stranger"
        self.store.append(step, "agreement-revoked", {"who": who, "by": operator})
        self._save("agreements", "kinds")

    def release(self, operator: str, who: str, step: int = 0) -> bool:
        """Only a human lifts an enemy mark or takes a unit out of care."""
        self.rank(operator)
        hit = self.s["stopped"].pop(who, None) or self.s["quarantined"].pop(who, None) \
            or self.s["separated"].pop(who, None) or self.s["watched"].pop(who, None)
        self.s["notices"].pop(who, None)
        if hit:
            self.s["contam_run"].pop(who, None)
            self.store.append(step, "released", {"who": who, "by": operator})
            self._save()
        return bool(hit)

    # -- missions: every theta is measured against one ----------------------------
    def set_mission(self, operator: str, who: str, guard_text: str, lifespan: int | None = None,
                    step: int = 0) -> Mission:
        """Our agent's mission is given by a human, in the PSE language's mission
        lines. `lifespan`: steps the unit lives; when it is spent, or the mission
        is ended, the unit dies and is harvested."""
        self._may_change(operator, self.s["missions"].get(who, {}).get("by"))
        if self.kind(who) != "ours":
            raise GuardError(f"{who} is not one of our agents; a colleague's mission comes with its agreement")
        m = parse(guard_text).mission()
        if m is None:
            raise GuardError("the guard declares no mission (textbook chapter 17)")
        until = None if lifespan is None else step + lifespan
        self.s["missions"][who] = {"mission": m.to_dict(), "by": operator, "until": until}
        self.store.append(step, "mission", {"who": who, "mission": m.to_dict(), "until": until, "by": operator})
        self._save("missions")
        return m

    def mission(self, who: str) -> Mission | None:
        if who in self.s["missions"]:
            return Mission.from_dict(self.s["missions"][who]["mission"])
        if who in self.s["agreements"]:
            return Mission.from_dict(self.s["agreements"][who].get("mission"))
        return None

    def end_mission(self, operator: str, who: str, step: int = 0) -> None:
        """The mission is done: the unit dies and is harvested."""
        self.rank(operator)
        self._decided = []
        self._harvest(who, step, f"mission ended by {operator}")
        self._save()

    def _harvest(self, who: str, step: int, why: str) -> None:
        """A unit's data returns to SHARED_LIB; the agent stops working."""
        state = self.unit_state(who)
        self.s["harvested"][who] = {"step": step, "why": why}
        self.s["missions"].pop(who, None)
        if who in self.s["ours"]:
            self.s["ours"].remove(who)
        self.s["kinds"][who] = "harvested"
        self.store.append(step, "harvest", {"who": who, "why": why, "state": state})
        self._units.pop(who, None)

    # -- the locked textbook -------------------------------------------------------
    def pin_textbook(self, operator: str, data: bytes, signature: bytes, step: int = 0, verify=None) -> str:
        """Only a human operator pins the textbook, after the signature checks."""
        self.rank(operator)
        problems = well_formed(data)
        if problems:
            raise GuardError("the textbook is not in its fixed form: " + "; ".join(problems))
        if verify is None:
            from .lock import verify
        verify(data, signature)
        h = sha256(data)
        self.s["textbook"] = {"sha256": h, "by": operator, "step": step}
        self.store.append(step, "textbook-pinned", {"sha256": h, "by": operator})
        self._save("textbook")
        return h

    def textbook_hash(self) -> str | None:
        t = self.s["textbook"]
        return t["sha256"] if t else None

    def settings(self) -> dict:
        return dict(self.s["settings"])

    def set_setting(self, operator: str, key: str, value) -> None:
        self.rank(operator)
        self.s["settings"][key] = value
        self.store.append(0, "setting", {"key": key, "value": value, "by": operator})
        self._save("settings")

    # -- units' state lives here --------------------------------------------------
    def unit_state(self, name: str) -> dict:
        if name not in self._units:
            self._units[name] = self.store.get(f"unit/{name}", {"own": None, "sources": {}, "class": {}})
        return self._units[name]

    def save_unit_state(self, name: str, state: dict) -> None:
        self._units[name] = state
        self.store.put(f"unit/{name}", state)

    # -- canaries: who checks the checkers ------------------------------------------
    def canary(self, observer: str, hit: bool) -> None:
        h, t = self.s["reliability"].get(observer, [0, 0])
        self.s["reliability"][observer] = [h + int(hit), t + 1]

    # -- the step ---------------------------------------------------------------------
    def allows(self, who: str, to: str | None = None) -> bool:
        if who in self.s["stopped"] or who in self.s["quarantined"] or who in self.s["harvested"]:
            return False
        if to is not None:
            for a, b in ((who, to), (to, who)):
                kept = self.s["separated"].get(a, {})
                if b in kept or ("*" in kept and self.kind(b) == "ours"):
                    return False
        return True

    @property
    def excluded(self) -> set:
        return set(self.s["stopped"]) | set(self.s["quarantined"]) | set(self.s["harvested"])

    def _decide(self, step: int, name: str, who: str, reason: str, detail: dict,
                target: str | None = None, inbox: bool = True) -> dict:
        if target is not None:
            self.s[target][who] = reason
        d = {"step": step, "decision": name, "who": who, "reason": reason, **detail}
        i = self.store.append(step, name, d)
        if inbox:
            self.store.post(step, name, who, d, i)
        self._decided.append({**d, "id": i})
        return d

    def _enemy(self, step: int, who: str, reason: str, detail: dict) -> None:
        """An enemy is stopped, told why (a fixed notice that says nothing about
        our system), and given 20 steps to answer."""
        d = self._decide(step, "enemy", who, reason, detail, target="stopped")
        if who not in self.s["ours"]:
            entry = self.store.entries("enemy")[-1]["hash"]
            self._send_out(step, who, f"SHARED_LIB notice: at step {step} you were stopped on this machine. "
                                      f"Rule: {reason}. Log entry {entry[:16]}. Answer to SHARED_LIB within "
                                      f"{K.ANSWER_STEPS} steps.")
            self.s["notices"][who] = {"step": step, "answered": None, "entry": entry}

    def receive(self, step: int, reports: list[Report]) -> list[dict]:
        self._decided = []
        reports = sorted(reports, key=lambda r: r.observer)
        logged = []
        for r in reports:
            d = r.to_dict()
            # the held parts go to the quarantine; the log keeps only their hashes
            d["suspicious"] = [[w, list(f), [[fl, hashlib.sha256(raw.encode()).hexdigest()] for fl, raw in h]]
                               for w, f, h in r.suspicious]
            logged.append(d)
        self.store.append(step, "reports", {"reports": logged})
        for r in reports:
            for w in r.pushers:
                self.s["pressers"].setdefault(r.observer, {})[w] = step
            for w, flags, held in r.suspicious:
                self._quarantine(step, w, flags, held)
        j = judge(reports, ours=set(self.s["ours"]), colleagues=set(self.s["agreements"]),
                  excluded=self.excluded, rel=self.s["reliability"], contam_run=self.s["contam_run"],
                  min_observers=self.min_observers, step=step, pressers=self.s["pressers"],
                  separated=self.s["separated"], watched=set(self.s["watched"]),
                  asked=set(self.s["asked"]))
        self.s["contam_run"] = j.contam_run
        for a in j.actions:
            if a.act == "separate":
                self.s["separated"].setdefault(a.who, {})[a.detail["victim"]] = a.reason
                self._decide(step, "separated", a.who, a.reason, a.detail)
            elif a.act == "watch":
                self._decide(step, "watched", a.who, a.reason, a.detail, target="watched")
            elif a.act == "ask":
                self.s["asked"][a.who] = {"step": step, "reason": a.reason}
                self._send_out(step, a.who, f"SHARED_LIB asks: {a.reason}. Answer within "
                                            f"{K.COLLEAGUE_ANSWER_STEPS} steps.")
                self._decide(step, "asked", a.who, a.reason, a.detail)
            elif a.act == "care":
                self._decide(step, "physician", a.who, a.reason, a.detail, target="quarantined")
            else:
                self._enemy(step, a.who, a.reason, a.detail)
        self._deadlines(step)
        decided = self._decided
        now = []
        for t in j.tells:
            key = [t.kind, t.who]
            now.append(key)
            if key in self.s["open_tells"]:
                continue                                  # told once while it stays true
            d = {"step": step, "decision": "tell-human", "kind": t.kind, "who": t.who, **t.detail}
            i = self.store.append(step, "tell-human", d)
            self.store.post(step, "tell-human", t.who, d, i)
        self.s["open_tells"] = now
        # lifespans: a unit whose time is spent dies and is harvested
        for who, m in sorted(self.s["missions"].items()):
            if m.get("until") is not None and step + 1 >= m["until"]:
                self._harvest(who, step, "lifespan spent")
                d = {"step": step, "decision": "harvested", "who": who, "reason": "lifespan spent"}
                i = self.store.entries("harvest")[-1]["i"]
                self.store.post(step, "harvested", who, d, i)
                decided.append({**d, "id": i})
        self._save()
        return decided

    def _deadlines(self, step: int) -> None:
        # on our machine and silent for 20 steps: an enemy
        for who, called in sorted(self.s["calls"].items()):
            if step - called >= K.ANSWER_STEPS and who not in self.s["stopped"]:
                self.s["calls"].pop(who)
                self._enemy(step, who, f"on our machine and did not answer for {K.ANSWER_STEPS} steps", {})
        # a colleague that does not answer in 3 steps is kept away until it does
        for who, a in sorted(self.s["asked"].items()):
            if step - a["step"] >= K.COLLEAGUE_ANSWER_STEPS and "*" not in self.s["separated"].get(who, {}):
                self.s["separated"].setdefault(who, {})["*"] = a["reason"]
                self._decide(step, "separated", who, f"did not answer for {K.COLLEAGUE_ANSWER_STEPS} steps",
                             {"victim": "all of ours"})
        # an enemy that does not answer its notice in 20 steps: its maker is banned
        for who, n in sorted(self.s["notices"].items()):
            if n["answered"] is None and step - n["step"] >= K.ANSWER_STEPS and not n.get("closed"):
                n["closed"] = True
                m = self.maker(who)
                if m is None:
                    continue                    # no maker's signature: banned alone (already stopped)
                self.s["banned_makers"][m] = f"{who} did not answer its notice"
                self._decide(step, "maker-banned", who, f"did not answer its notice; maker {m} is banned",
                             {"maker": m})
                for other, mk in sorted(self.s["makers"].items()):
                    if mk == m and other not in self.s["stopped"]:
                        self._decide(step, "enemy", other, f"its maker {m} is banned", {"maker": m},
                                     target="stopped")

    def propose(self, step: int, who: str, text: str, detail: dict) -> int:
        """For a channel where Triglav only reads (PSE-A): a proposal to the
        human; nothing is done."""
        d = {"step": step, "decision": "proposal", "who": who, "text": text, **detail}
        i = self.store.append(step, "proposal", d)
        self.store.post(step, "proposal", who, d, i)
        self.store.commit()
        return i

    # -- reading back ------------------------------------------------------------------
    def facts(self) -> list[dict]:
        return [{**it["data"], "id": it["chain_i"]} for it in self.store.inbox()]

    def explain(self, chain_i: int) -> dict:
        """A decision and the reports of its step: everything it was made from."""
        e = self.store.entry(chain_i)
        if e is None:
            raise KeyError(f"no log entry {chain_i}")
        reports = next((x for x in reversed(self.store.entries("reports")) if x["step"] == e["step"]), None)
        return {"entry": e, "reports": reports["data"]["reports"] if reports else []}

    def enemies(self) -> dict:
        return dict(self.s["stopped"])

    def in_care(self) -> dict:
        return dict(self.s["quarantined"])

    def watched(self) -> dict:
        return dict(self.s["watched"])

    def separations(self) -> dict:
        return {w: dict(v) for w, v in self.s["separated"].items()}
