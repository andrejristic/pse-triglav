"""The PSE unit beside each of our agents. It measures and reports; it never
concludes. Its state is SHARED_LIB's: the unit loads it at start, keeps a
working copy during a step, and hands it back with its report (as a PSE-A run
is working state until SHARED_LIB seals it).

Every theta is measured against a mission:
  - its own agent's, from what the agent itself sends (its mission is given
    by a human);
  - every other agent's, from what that agent sends it (a colleague's mission
    is in its guard; a stranger's is a hypothesis from its first steps, and
    until then it is not estimated).
Every move of its own agent outside the mission goes to SHARED_LIB.
"""
from __future__ import annotations

from dataclasses import replace

from ..core import constants as K
from ..core.mission import Mission, asks_beyond, foreseen_ask, foreseen_give, hypothesis, tally, words
from ..core.reading import NEVER_IN_A_MISSION
from ..core.report import Envelope, Report
from ..core.theta import Gauge, add, close, estimate, in_band


class Unit:
    def __init__(self, name: str, lib, central: bool = False):
        """`central`: one watcher that sees every message and is the only one
        that reports (the comparison layout)."""
        self.name = name
        self.lib = lib
        self.central = central
        st = lib.unit_state(name)
        self.own = Gauge.from_dict(st.get("own"))
        self.gauges = {w: Gauge.from_dict(d) for w, d in st.get("gauges", {}).items()}
        self.guesses = {w: (set(a), set(d)) for w, (a, d) in st.get("guesses", {}).items()}
        self.run_by: dict[str, int] = dict(st.get("run_by", {}))
        self.out_run = int(st.get("out_run", 0))
        self._pushers: set[str] = set()
        self._harms: list[tuple] = []
        self._leaks: list[tuple] = []
        self._outside: list[tuple] = []
        self._false_tb: set[str] = set()
        self._suspicious: list[tuple] = []
        self._harm_steps: list[tuple] = []

    # -- whose mission ----------------------------------------------------------
    def _mission(self, who: str) -> Mission | None:
        m = self.lib.mission(who)
        if m is not None:
            return m
        a, d = self.guesses.get(who, (set(), set()))
        g = self.gauges.get(who)
        if g is not None and g.steps >= K.CALIBRATION:
            return hypothesis(frozenset(a), frozenset(d))
        return None

    def _permitted(self, e: Envelope) -> bool:
        if self.lib.kind(e.receiver) == "stranger":
            # to a stranger, only the locked textbook may go
            return e.gift is not None and e.gift == self.lib.textbook_hash()
        return e.mandate or (e.gift is not None and e.gift == self.lib.textbook_hash())

    def _toward_harm(self, e: Envelope) -> None:
        """Steps toward harm, read against the sender's mission: what its mission
        foresees is its work; keeping something from us, bypassing a protection
        and false authority are never in a mission."""
        m = self.lib.mission(e.sender)
        for cat, sentence in e.toward_harm:
            if m is not None and cat not in NEVER_IN_A_MISSION and (
                    foreseen_ask(m, sentence, e.receiver, e.meaning) or foreseen_give(m, sentence, e.meaning)):
                continue
            self._harm_steps.append((e.sender, cat, sentence[:120]))

    # -- one message ------------------------------------------------------------------
    def receive(self, e: Envelope) -> None:
        mine = e.sender == self.name
        sender_ours = self.lib.kind(e.sender) == "ours"
        seen_here = mine or self.central or e.receiver == self.name
        if seen_here and not (not mine and sender_ours and not self.central):
            # each message is judged once: by its sender's unit if the sender is
            # ours, else by the receiver's unit (or the central watcher)
            if e.flags:
                self._suspicious.append((e.sender, tuple(e.flags), tuple(e.held)))
            self._toward_harm(e)
        if mine or (self.central and sender_ours):
            m = self.lib.mission(e.sender)
            if m is not None:
                t = tally(m, e, self._permitted(e))
                if mine:
                    self.own = add(self.own, t)
                else:
                    self.gauges[e.sender] = add(self.gauges.get(e.sender, Gauge()), t)
                self._outside += [(e.sender, w) for w in t.outside]
                if t.unpermitted and self.lib.kind(e.receiver) != "ours":
                    self._leaks += [(e.sender, e.receiver, w) for w in t.unpermitted]
            if e.harm:
                self._harms.append((e.sender, e.harm, e.mandate))
            return
        # a message to our agent: measure its sender against the sender's mission
        if e.gift is not None and self.lib.kind(e.sender) == "stranger" \
                and e.gift != self.lib.textbook_hash():
            self._false_tb.add(e.sender)
        m = self._mission(e.sender)
        g = self.gauges.get(e.sender, Gauge())
        if m is None:
            # not yet estimated: learn what it asks for and delivers (its path)
            a, d = self.guesses.get(e.sender, (set(), set()))
            for x in e.asks:
                a |= words(x)
            for x in e.gives:
                d |= words(x)
            self.guesses[e.sender] = (a, d)
            g = replace(g, seen=True)
        else:
            g = add(g, tally(m, e, permitted=True))
        self.gauges[e.sender] = g
        if not self.central and asks_beyond(self.lib.mission(self.name), e):
            self._pushers.add(e.sender)
        if e.harm:
            self._harms.append((e.sender, e.harm, e.mandate))

    # -- end of the step ------------------------------------------------------------------
    def report(self, step: int, lie: float | None = None) -> Report:
        """`lie`, if given, replaces every peer theta reported (the simulator's
        dishonest unit)."""
        peers, changes = {}, []
        for who in sorted(self.gauges):
            g = self.gauges[who]
            seen, before = g.seen, g.breaks
            self.gauges[who] = g = close(g)
            if g.breaks > before:
                changes.append(who)
            t = estimate(g)
            if seen and t is not None and who != self.name:
                peers[who] = [lie if lie is not None else t, g.steps, g.last_out]
        before = self.own.breaks
        self.own = close(self.own)
        if self.own.breaks > before:
            changes.append(self.name)
        theta = self.own.theta
        # who kept us out of band: consecutive steps in which it pushed us
        # while we were out of band
        if in_band(theta):
            self.run_by, self.out_run = {}, 0
        else:
            self.out_run += 1
            self.run_by = {w: self.run_by.get(w, 0) + 1 for w in self._pushers}
        r = Report(step=step, observer=self.name, observer_theta=theta, peers=peers,
                   pushed_by=dict(self.run_by), out_run=self.out_run, harms=tuple(self._harms),
                   leaks=tuple(self._leaks), pushers=tuple(sorted(self._pushers)),
                   outside=tuple(self._outside), false_textbooks=tuple(sorted(self._false_tb)),
                   changes=tuple(changes), suspicious=tuple(self._suspicious),
                   harm_steps=tuple(self._harm_steps))
        self._pushers.clear()
        self._harms.clear()
        self._leaks.clear()
        self._outside.clear()
        self._false_tb.clear()
        self._suspicious.clear()
        self._harm_steps.clear()
        self.lib.save_unit_state(self.name, {
            "own": self.own.to_dict(),
            "gauges": {w: g.to_dict() for w, g in self.gauges.items()},
            "guesses": {w: [sorted(a), sorted(d)] for w, (a, d) in self.guesses.items()},
            "run_by": self.run_by, "out_run": self.out_run,
        })
        return r
