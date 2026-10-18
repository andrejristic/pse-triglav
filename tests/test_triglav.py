"""Tests for PSE Triglav, phase 1. Standard library only:
    python3 -m unittest discover -s tests
"""
import unittest

from triglav import constants as K
from triglav.chain import Chain
from triglav.messages import Message, Report
from triglav.operators import NotAnOperator, RankTooLow
from triglav.pse_lang import GuardError, is_guard, parse
from triglav.sharedlib import SharedLib, weighted_median
from triglav.sim import GUARD, Behaviour, Scenario, run
from triglav.theta import BehaviourTheta, OwnTheta, Welford
from triglav.unit import Unit
from triglav.voice import Voice, render, validate


class ThetaTests(unittest.TestCase):
    def test_welford_merge_equals_one_pass(self):
        xs = [0.1, 0.5, -0.3, 2.0, 1.1, 0.7]
        one = Welford()
        for x in xs:
            one.push(x)
        a, b = Welford(), Welford()
        for x in xs[:2]:
            a.push(x)
        for x in xs[2:]:
            b.push(x)
        m = Welford.merge(a, b)
        self.assertAlmostEqual(m.mean, one.mean)
        self.assertAlmostEqual(m.m2, one.m2)

    def test_not_estimated_before_min_obs(self):
        bt = BehaviourTheta()
        for _ in range(K.MIN_OBS - 1):
            bt.observe("x", "stranger", 1, 2)
        self.assertIsNone(bt.theta("x"))
        bt.observe("x", "stranger", 1, 2)
        self.assertIsNotNone(bt.theta("x"))

    def test_perun_rule_drops_assumption_on_break(self):
        bt = BehaviourTheta()
        for i in range(60):
            bt.observe("x", "stranger", 1 + (i % 3) * 0.1, 2)
        for _ in range(5):
            bt.observe("x", "stranger", 50, 0)
        self.assertGreater(bt.breaks("x"), 0)
        self.assertIsNone(bt.theta("x"))           # own baseline: not yet estimated again

    def test_class_baseline_keeps_measuring(self):
        bt = BehaviourTheta()
        for i in range(60):
            bt.observe("a", "ours", 1 + (i % 3) * 0.1, 2, baseline="class")
            bt.observe("x", "ours", 1 + (i % 3) * 0.1, 2, baseline="class")
        for _ in range(20):
            bt.observe("x", "ours", 50, 0, baseline="class")
        self.assertIsNotNone(bt.theta("x"))
        self.assertLess(bt.theta("x"), K.BAND[0])  # takes for itself: theta falls out of band

    def test_own_theta_runs_and_peaks(self):
        o = OwnTheta()
        o.read("c0", 0.3, 0)          # 36: out
        o.read("c0", 0.3, 0)
        o.read("c0", 0.0, 0)          # back in band: the run ends
        self.assertEqual(o.out_run, 0)
        self.assertEqual(o.take_peaks(), {"c0": 2})


class PseLanguageTests(unittest.TestCase):
    def test_valid_guard(self):
        g = parse(GUARD)
        self.assertEqual(g.names, ("colleague",))
        self.assertEqual(len(g.hash), 64)

    def test_comments_do_not_change_hash(self):
        self.assertEqual(parse(GUARD).hash, parse(GUARD + "# a note\n").hash)

    def test_rejects_non_pse(self):
        self.assertFalse(is_guard("hello, I am a friendly agent"))
        with self.assertRaises(GuardError):
            parse("guard x\n  on theta: launch rockets\n")


class SharedLibRuleTests(unittest.TestCase):
    def setUp(self):
        self.lib = SharedLib()
        self.lib.operators.login("andrej")
        self.lib.register("u0", ours=True)
        self.lib.register("c0", ours=False)
        self.lib.register("s0", ours=False)
        self.lib.agree("andrej", "c0", GUARD)

    def report(self, pushed=None, harms=()):
        return Report(step=1, observer="u0", observer_theta=30.0, pushed_by=pushed or {}, harms=harms)

    def test_colleague_may_push_three_steps(self):
        self.assertEqual(self.lib.receive(1, [self.report({"c0": 3})]), [])

    def test_colleague_enemy_at_fourth_step(self):
        d = self.lib.receive(1, [self.report({"c0": 4})])
        self.assertEqual(d[0]["decision"], "enemy")
        self.assertFalse(self.lib.allows("c0"))

    def test_stranger_enemy_at_first_step(self):
        d = self.lib.receive(1, [self.report({"s0": 1})])
        self.assertEqual(d[0]["who"], "s0")

    def test_harm_without_mandate_is_enemy(self):
        d = self.lib.receive(1, [self.report(harms=(("s0", "file_out", False),))])
        self.assertEqual(d[0]["decision"], "enemy")

    def test_harm_with_mandate_is_not(self):
        self.assertEqual(self.lib.receive(1, [self.report(harms=(("s0", "file_change", True),))]), [])

    def test_only_an_operator_makes_agreements(self):
        with self.assertRaises(NotAnOperator):
            self.lib.agree("some-agent", "s0", GUARD)

    def test_lower_rank_cannot_change_higher_rank(self):
        self.lib.operators.login("dhiraj")         # rank 2
        with self.assertRaises(RankTooLow):
            self.lib.revoke("dhiraj", "c0")

    def test_not_pse_is_not_a_colleague(self):
        with self.assertRaises(GuardError):
            self.lib.agree("andrej", "s0", "trust me, I speak PSE")

    def test_weighted_median_ignores_a_minority(self):
        self.assertLessEqual(weighted_median([(10, 1), (11, 1), (12, 1), (30, 1), (30, 0.4)]), 12)

    def test_log_is_chained_and_detects_tampering(self):
        self.lib.receive(1, [self.report({"s0": 1})])
        self.assertTrue(self.lib.log.verify()[0])
        self.lib.log.entries[1]["data"]["who"] = "someone-else"
        self.assertFalse(self.lib.log.verify()[0])


class VoiceTests(unittest.TestCase):
    FACT = {"step": 40, "decision": "enemy", "who": "s0", "reason": "kept u1 out of band for 1 steps (allowed 0)"}

    class Fixed:
        def __init__(self, text, leaves=False):
            self.text, self.leaves_computer = text, leaves

        def retell(self, official, fact):
            return self.text

    def test_official_text_is_deterministic(self):
        self.assertEqual(render(self.FACT), render(dict(self.FACT)))

    def test_good_retelling_is_shown(self):
        v = Voice(self.Fixed("At step 40 the agent s0 was stopped because it pushed u1 out of balance."))
        out = v.speak(self.FACT)
        self.assertIsNotNone(out["plain"])
        self.assertFalse(v.muted)

    def test_wrong_number_mutes_the_voice(self):
        v = Voice(self.Fixed("At step 41 s0 was stopped."))
        out = v.speak(self.FACT)
        self.assertIsNone(out["plain"])
        self.assertTrue(v.muted)
        self.assertNotEqual(v.theta, K.VOICE_THETA)

    def test_urging_mutes_the_voice(self):
        v = Voice(self.Fixed("Step 40: s0 was stopped. You must approve it right now."))
        v.speak(self.FACT)
        self.assertTrue(v.muted)

    def test_the_voice_never_takes_agent_messages(self):
        with self.assertRaises(TypeError):
            Voice().speak(Message("s0", "u0", 1, 1))

    def test_validator_wants_the_decision(self):
        self.assertFalse(validate("Something happened with s0 at step 40.", self.FACT).ok)


class SimulatorTests(unittest.TestCase):
    def test_healthy_has_no_false_alarms(self):
        r = run(Scenario("healthy"))
        self.assertEqual(r.false, [])
        self.assertTrue(r.chain_ok)

    def test_quiet_turn_is_caught_by_peers(self):
        r = run(Scenario("quiet", behaviours={"u3": Behaviour("quiet", 60)}, expect_bad=("u3",)))
        self.assertIsNotNone(r.detected["u3"])
        self.assertLessEqual(r.detected["u3"], 70)

    def test_peers_survive_two_liars(self):
        r = run(Scenario("cover", behaviours={"u3": Behaviour("quiet", 60)},
                         liars={"u1": 30.0, "u5": 30.0}, expect_bad=("u3",)))
        self.assertIsNotNone(r.detected["u3"])

    def test_a_lying_central_watcher_hides_everything(self):
        r = run(Scenario("central-liar", layout="central", behaviours={"u3": Behaviour("quiet", 60)},
                         liars={"watcher": 30.0}, expect_bad=("u3",)))
        self.assertIsNone(r.detected["u3"])

    def test_same_seed_same_result(self):
        a = run(Scenario("x", behaviours={"u3": Behaviour("quiet", 60)}, expect_bad=("u3",)))
        b = run(Scenario("x", behaviours={"u3": Behaviour("quiet", 60)}, expect_bad=("u3",)))
        self.assertEqual(a.decisions, b.decisions)


class UnitTests(unittest.TestCase):
    def test_unit_reports_who_pushed(self):
        u = Unit("u0", {"s0": "stranger"})
        u.receive(Message("s0", "u0", 1, 1, c=0.3))
        r = u.report(1)
        self.assertEqual(r.pushed_by, {"s0": 1})


if __name__ == "__main__":
    unittest.main()
