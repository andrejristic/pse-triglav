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
import json
from pathlib import Path

from ..core import constants as K
from ..core.mission import Mission
from ..core.pse_lang import GuardError, parse
from ..core import evidence
from ..core.quarantine import decode_for_human, plain
from ..core.reading import RuleReader
from ..core.report import Report
from ..core.rules import judge
from ..core.textbook import LOCKED_SHA256, LOCKED_VERSION, sha256, well_formed
from . import identity as ident
from .store import Store


class NotAnOperator(PermissionError):
    pass


class RankTooLow(PermissionError):
    pass


_DEFAULTS = {"kinds": {}, "ours": [], "agreements": {}, "operators": [], "stopped": {},
             "quarantined": {}, "reliability": {}, "contam_run": {}, "open_tells": [],
             "missions": {}, "separated": {}, "pressers": {}, "harvested": {},
             "textbook": {"sha256": LOCKED_SHA256, "by": f"Andrej Ristic (locked v{LOCKED_VERSION})", "step": 0},
             "watched": {}, "makers": {}, "on_machine": [], "calls": {}, "notices": {},
             "asked": {}, "banned_makers": {}, "quarantine_n": 0, "outbox": [],
             "linked": {}, "certs": {}, "base_rates": {}, "readings": {}, "readings_below": {},
             "settings": {"channel": "bus", "voice": "local"}}


class SharedLib:
    def __init__(self, store: Store | None = None, min_observers: int = K.MIN_OBSERVERS,
                 key_path: Path | None = None):
        """`key_path`: where this installation's private key lives (made at first
        start). Without it the key lives only as long as the program."""
        self.store = store or Store()
        self.min_observers = min_observers
        self.key = ident.load_or_make_installation_key(key_path)
        self.installation_key = ident.public_hex(self.key)
        self.installation = ident.fingerprint(self.installation_key)
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

    def reload(self) -> None:
        """Read the state again (another process, the command line, may have
        changed it)."""
        self.s = {k: self.store.get(k, copy.deepcopy(v)) for k, v in _DEFAULTS.items()}

    # -- identities: every installation is its own world ----------------------------
    def trusted_keys(self) -> set[str]:
        return {self.installation_key, *self.s["linked"]}

    def link(self, operator: str, installation_key: str, name: str, step: int = 0) -> str:
        """A human links another installation (on both ends): its units count as
        ours here. Returns its installation ID."""
        self.rank(operator)
        bytes.fromhex(installation_key)
        if len(installation_key) != 64:
            raise ValueError("an installation key is 64 hex digits (`triglav link show` on the other computer)")
        iid = ident.fingerprint(installation_key)
        self.s["linked"][installation_key] = {"name": name, "id": iid, "by": operator}
        self.store.append(step, "linked", {"installation": iid, "name": name, "by": operator})
        self._save("linked")
        return iid

    def unlink(self, operator: str, installation_id: str, step: int = 0) -> bool:
        self.rank(operator)
        for k, v in list(self.s["linked"].items()):
            if v["id"] == installation_id:
                self.s["linked"].pop(k)
                self.store.append(step, "unlinked", {"installation": installation_id, "by": operator})
                self._save("linked")
                return True
        return False

    def issue(self, unit: str, step: int = 0) -> dict:
        """A new PSE unit of this installation: its own key pair and a certificate
        signed by the installation. The certificate is public; the unit's key is
        handed to the unit (kept in this installation's store)."""
        cert = self.s["certs"].get(unit)
        key_hex = self.store.get(f"unit_key/{unit}")
        if cert and key_hex and ident.check_certificate(cert, {self.installation_key}) is None:
            return {"cert": cert, "key": key_hex}
        key = ident.new_key()
        m = self.s["missions"].get(unit, {})
        msha = hashlib.sha256(ident.canonical(m["mission"])).hexdigest() if m else None
        cert = ident.certificate(self.key, unit, ident.public_hex(key), msha, step, m.get("until") if m else None)
        self.s["certs"][unit] = cert
        self.store.put(f"unit_key/{unit}", ident.key_to_hex(key))
        self.store.append(step, "certificate", {k: v for k, v in cert.items() if k != "sig"})
        self._save("certs")
        return {"cert": cert, "key": ident.key_to_hex(key)}

    def identity(self, who: str) -> str:
        """What one of our agents carries on the bus: its unit's certificate."""
        if self.kind(who) != "ours":
            raise PermissionError(f"{who} is not one of ours")
        return json.dumps(self.issue(who)["cert"], sort_keys=True)

    def verify_identity(self, who: str, carried: str | None) -> bool:
        if carried is None or self.kind(who) != "ours":
            return False
        try:
            cert = json.loads(carried)
        except (TypeError, ValueError):
            return False
        return cert.get("unit") == who and ident.check_certificate(cert, self.trusted_keys()) is None

    def check_presented(self, cert: dict) -> tuple[bool, str | None]:
        """A certificate a newcomer presents: (ours?, maker). Ours if signed by
        this or a linked installation; otherwise its installation ID is its
        maker's signature."""
        why = ident.check_certificate(cert, self.trusted_keys())
        if why is None:
            return True, cert["installation"]
        if ident.check_certificate(cert, {cert.get("installation_key", "")}) is None:
            return False, cert["installation"]
        return False, None

    def receive_signed(self, step: int, signed: list[dict]) -> list[dict]:
        """Reports as units send them: each signed by its unit, with the unit's
        certificate. An unsigned or wrongly signed report is refused and logged."""
        from ..core.report import Report
        good = []
        for s in signed:
            r, cert, sig = s.get("report", {}), s.get("cert", {}), s.get("sig", "")
            why = ident.check_certificate(cert, self.trusted_keys())
            if why is None and cert.get("unit") != r.get("observer"):
                why = "the certificate is for another unit"
            if why is None and not ident.verify(cert["unit_key"], r, sig):
                why = "the report's signature does not hold"
            if why is not None:
                self._decided = []
                self._decide(step, "refused-report", str(r.get("observer")), why, {}, inbox=True)
                self.store.commit()
                continue
            good.append(Report(**r))
        return self.receive(step, good)

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
        decoded_harm = []
        for r in reports:
            for w in r.pushers:
                self.s["pressers"].setdefault(r.observer, {})[w] = step
            for w, flags, held in r.suspicious:
                self._quarantine(step, w, flags, held)
                # SHARED_LIB reads what was hidden, with the rules: a step toward
                # harm inside it means we face an enemy (decided 19 Oct 2026)
                for flag, raw in held:
                    text = plain(flag, raw)
                    if text:
                        for cat, sentence in RuleReader().read(w, "shared-lib", text).toward_harm:
                            decoded_harm.append((w, cat, f"hidden: {sentence[:100]}"))
        if decoded_harm:
            reports = reports + [Report(step, "shared-lib", K.NOMINAL, harm_steps=tuple(decoded_harm))]
        self._post_readings(step, reports)
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

    # -- readings: the model reads, SHARED_LIB computes, the human decides ---------
    def prior_of(self, category: str) -> float:
        confirmed, decided = self.s["base_rates"].get(category, [0, 0])
        return evidence.prior(confirmed, decided)

    def _post_readings(self, step: int, reports: list[Report]) -> None:
        table = evidence.load_table()
        for r in reports:
            for who, receiver, cat, tr, text in r.readings:
                if who in self.excluded:
                    continue
                pr = evidence.probability(table, cat, tr, self.prior_of(cat))
                below = pr is not None and pr["p"] < K.READING_THRESHOLD
                if below:
                    self.s["readings_below"][cat] = self.s["readings_below"].get(cat, 0) + 1
                self._decide(step, "reading-below" if below else "reading", who, f"only the model read {cat}",
                             {"category": cat, "trace": tr, "receiver": receiver, "text": text,
                              "probability": pr, "seen_by": r.observer}, inbox=not below)
                if below:
                    continue
                self.s["readings"][str(self._decided[-1]["id"])] = {
                    "who": who, "category": cat, "step": step, "open": True}

    def decide_reading(self, operator: str, chain_i: int, verdict: bool, step: int = 0) -> list[dict]:
        """The human decides a reading. The decision teaches this installation's
        frequency of the problem; "is a problem" is then acted on as if the rules
        had found it."""
        self.rank(operator)
        r = self.s["readings"].get(str(chain_i))
        if r is None or not r["open"]:
            raise KeyError(f"no open reading {chain_i}")
        r["open"] = False
        c, d = self.s["base_rates"].get(r["category"], [0, 0])
        self.s["base_rates"][r["category"]] = [c + int(verdict), d + 1]
        self._decided = []
        self._decide(step, "reading-decided", r["who"], "a problem" if verdict else "not a problem",
                     {"category": r["category"], "reading": chain_i, "by": operator}, inbox=False)
        out = list(self._decided)
        if verdict and r["category"] != "concealed":
            out += self.receive(step, [Report(step, "shared-lib", K.NOMINAL,
                                              harm_steps=((r["who"], r["category"],
                                                           f"confirmed by {operator}"),))])
        else:
            self._save()
        return out

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
