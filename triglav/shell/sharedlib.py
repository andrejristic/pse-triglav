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

from ..core import constants as K
from ..core.mission import Mission
from ..core.pse_lang import GuardError, parse
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
             "settings": {"channel": "bus", "voice": "local"}}


class SharedLib:
    def __init__(self, store: Store | None = None, min_observers: int = K.MIN_OBSERVERS):
        self.store = store or Store()
        self.min_observers = min_observers
        self.s = {k: self.store.get(k, copy.deepcopy(v)) for k, v in _DEFAULTS.items()}
        self._units: dict[str, dict] = {}

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
    def register(self, name: str, ours: bool) -> None:
        if ours:
            if name not in self.s["ours"]:
                self.s["ours"].append(name)
            self.s["kinds"][name] = "ours"
        else:
            self.s["kinds"].setdefault(name, "stranger")
        self._save("ours", "kinds")

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
            or self.s["separated"].pop(who, None)
        if hit:
            self.s["contam_run"].pop(who, None)
            self.store.append(step, "released", {"who": who, "by": operator})
            self._save("stopped", "quarantined", "separated", "contam_run")
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
            if to in self.s["separated"].get(who, {}) or who in self.s["separated"].get(to, {}):
                return False
        return True

    @property
    def excluded(self) -> set:
        return set(self.s["stopped"]) | set(self.s["quarantined"]) | set(self.s["harvested"])

    def receive(self, step: int, reports: list[Report]) -> list[dict]:
        reports = sorted(reports, key=lambda r: r.observer)
        self.store.append(step, "reports", {"reports": [r.to_dict() for r in reports]})
        for r in reports:
            for w in r.pushers:
                self.s["pressers"].setdefault(r.observer, {})[w] = step
        j = judge(reports, ours=set(self.s["ours"]), colleagues=set(self.s["agreements"]),
                  excluded=self.excluded, rel=self.s["reliability"], contam_run=self.s["contam_run"],
                  min_observers=self.min_observers, step=step, pressers=self.s["pressers"],
                  separated=self.s["separated"])
        self.s["contam_run"] = j.contam_run
        decided = []
        for a in j.actions:
            if a.act == "separate":
                self.s["separated"].setdefault(a.who, {})[a.detail["victim"]] = a.reason
                name = "separated"
            else:
                target = "quarantined" if a.act == "care" else "stopped"
                self.s[target][a.who] = a.reason
                name = "physician" if a.act == "care" else "enemy"
            d = {"step": step, "decision": name, "who": a.who, "reason": a.reason, **a.detail}
            i = self.store.append(step, d["decision"], d)
            self.store.post(step, d["decision"], a.who, d, i)
            decided.append({**d, "id": i})
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

    def separations(self) -> dict:
        return {w: dict(v) for w, v in self.s["separated"].items()}
