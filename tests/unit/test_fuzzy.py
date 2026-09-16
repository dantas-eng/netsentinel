import unittest
from netsentinel.analysis.models import RiskInputs
from netsentinel.analysis.contracts import Reputation
from netsentinel.analysis.features import FeatureExtractor
from netsentinel.analysis.fuzzy.engine import infer, label_score
from netsentinel.analysis.fuzzy.membership import complementary, fuzzify, ramp_from
from netsentinel.analysis.fuzzy.rules import evaluate
from netsentinel.analysis.fuzzy import FuzzyRiskStrategy
from tests.support import FixedReputation, FixedBaseline


def inputs(c=0, f=0, r='known', d=0, ratio=None):
    return RiskInputs(c, f, r, d, ratio)


def snapshot(**updates):
    result = dict(incomplete=False, warming_up=False, observed_seconds=10,
                  devices={'aa': dict(bytes=1000, arp_requests=0, arp_replies=50)},
                  arp_claims=[])
    result.update(updates)
    return result


class MembershipTests(unittest.TestCase):
    def test_absent_not_zero(self):
        self.assertEqual(complementary(None, 5), {'low': 0, 'high': 0})
        self.assertEqual(complementary(0, 5), {'low': 1, 'high': 0})

    def test_linear_and_saturated(self):
        self.assertEqual(complementary(2.5, 5), {'low': 0.5, 'high': 0.5})
        self.assertEqual(complementary(7, 5), {'low': 0, 'high': 1})

    def test_invalid_present_values(self):
        for value in (-1, float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                complementary(value, 5)

    def test_unknown_reputation_all_zero(self):
        self.assertEqual(fuzzify(inputs(r=None))['reputation'], {'known': 0, 'new': 0})

    def test_ratio_floor_is_low(self):
        self.assertEqual(ramp_from(0.5, 0.5, 1.0), {'low': 1, 'high': 0})

    def test_ratio_one_is_high(self):
        self.assertEqual(ramp_from(1.0, 0.5, 1.0), {'low': 0, 'high': 1})

    def test_ratio_absent_both_zero(self):
        self.assertEqual(ramp_from(None, 0.5, 1.0), {'low': 0, 'high': 0})
        self.assertEqual(fuzzify(inputs(ratio=None))['ratio'], {'low': 0, 'high': 0})


class RuleTests(unittest.TestCase):
    def test_each_rule_in_isolation(self):
        cases = [('R1', inputs(c=1, f=None, r=None, d=None)),
                 ('R2', inputs(f=5, r='new', d=None)),
                 ('R3', inputs(f=5, d=None)),
                 ('R4', inputs(r='new', ratio=0.5)),
                 ('R5', inputs(ratio=0.5))]
        for rule, data in cases:
            with self.subTest(rule=rule):
                strengths = evaluate(fuzzify(data))
                self.assertEqual(strengths[rule], 1)
                self.assertEqual(sum(strengths.values()), 1)

    def test_or_works_with_frequency_absent(self):
        self.assertEqual(evaluate(fuzzify(inputs(f=None, r='new', d=1)))['R2'], 1)

    def test_and_requires_low_deviation_evidence(self):
        for reputation in ('new', 'known'):
            strengths = evaluate(fuzzify(inputs(r=reputation, d=None)))
            self.assertEqual(strengths['R4'], 0)
            self.assertEqual(strengths['R5'], 0)

    def test_fractional_min_max(self):
        strengths = evaluate(fuzzify(inputs(c=0.5, f=4, r='new', d=None)))
        self.assertEqual(strengths['R1'], 0.5)
        self.assertEqual(strengths['R2'], 0.5)

    def test_high_ratio_alone_fires_r2_for_new(self):
        self.assertEqual(evaluate(fuzzify(inputs(ratio=1.0, r='new')))['R2'], 1)

    def test_high_ratio_alone_fires_r3_for_known(self):
        self.assertEqual(evaluate(fuzzify(inputs(ratio=1.0)))['R3'], 1)


class InferenceTests(unittest.TestCase):
    def test_no_evidence_abstains_after_rules(self):
        result = infer(inputs(c=None, f=None, r=None, d=None))
        self.assertIsNone(result.score)
        self.assertIsNone(result.classification)
        self.assertEqual(result.reason, 'no_rule_activated')
        self.assertEqual(max(result.rule_strengths.values()), 0)

    def test_no_false_safe_without_baseline(self):
        result = infer(inputs(d=None))
        self.assertIsNone(result.score)
        self.assertEqual(result.reason, 'no_rule_activated')

    def test_r1_survives_all_other_missing(self):
        result = infer(inputs(c=0.5, f=None, r=None, d=None))
        self.assertGreaterEqual(result.score, 65)
        self.assertEqual(result.classification, 'suspeito')

    def test_r2_survives_missing_baseline(self):
        self.assertGreaterEqual(infer(inputs(f=5, r='new', d=None)).score, 65)

    def test_unknown_reputation_does_not_mean_new(self):
        result = infer(inputs(f=5, r=None, d=None))
        self.assertIsNone(result.score)

    def test_centroids_of_approved_shapes(self):
        # Áreas/centroides analíticos dos trapézios: 30 de área, 466 2/3 de momento.
        # ratio ausente: R4/R5 exigem ratio.low → abstenção (consequência prevista).
        self.assertIsNone(infer(inputs()).score)
        self.assertIsNone(infer(inputs(r='new')).score)
        self.assertAlmostEqual(infer(inputs(ratio=0.5)).score, 140 / 9, places=8)
        self.assertAlmostEqual(infer(inputs(r='new', ratio=0.5)).score, 50, places=8)
        self.assertAlmostEqual(infer(inputs(c=1)).score, 100 - 140 / 9, places=8)

    def test_thresholds_without_rounding(self):
        for value, label in [(34.999, 'confiável'), (35, 'desconhecido'),
                             (64.999, 'desconhecido'), (65, 'suspeito')]:
            self.assertEqual(label_score(value), label)

    def test_successive_calls_do_not_retain_memberships(self):
        infer(inputs(c=1))
        self.assertIsNone(infer(inputs(c=None, f=None, r=None, d=None)).score)

    def test_high_ratio_new_is_suspeito(self):
        result = infer(inputs(ratio=1.0, r='new'))
        self.assertEqual(result.rule_strengths['R2'], 1)
        self.assertEqual(result.classification, 'suspeito')

    def test_high_ratio_known_is_desconhecido(self):
        result = infer(inputs(ratio=1.0))
        self.assertEqual(result.rule_strengths['R3'], 1)
        self.assertEqual(result.classification, 'desconhecido')

    def test_absent_ratio_blocks_low_declaration(self):
        known = infer(inputs())
        self.assertEqual(known.rule_strengths['R4'], 0)
        self.assertEqual(known.rule_strengths['R5'], 0)
        self.assertIsNone(known.score)
        self.assertEqual(known.reason, 'no_rule_activated')
        newbie = infer(inputs(r='new'))
        self.assertEqual(newbie.rule_strengths['R4'], 0)
        self.assertEqual(newbie.rule_strengths['R5'], 0)
        self.assertIsNone(newbie.score)


class FeatureTests(unittest.TestCase):
    def make_extractor(self, baseline=100, reputation=Reputation.NEW):
        return FeatureExtractor(FixedReputation({'aa': reputation}), FixedBaseline({'aa': baseline}))

    def test_frequency_and_relative_deviation_units(self):
        result = self.make_extractor(baseline=50).extract(snapshot())['aa']
        self.assertEqual(result.arp_frequency, 5)
        self.assertEqual(result.volume_deviation, 1)

    def test_baseline_zero_missing_keeps_other_inputs(self):
        for baseline in (None, 0, -1, float('nan')):
            result = self.make_extractor(baseline).extract(snapshot())['aa']
            self.assertIsNone(result.volume_deviation)
            self.assertEqual(result.arp_frequency, 5)
            self.assertEqual(result.conflict, 0)

    def test_duplicate_claims_do_not_inflate_conflict(self):
        claim = dict(ip='192.0.2.1', claimed_mac='11', source_mac='aa', count=100)
        data = snapshot(arp_claims=[claim, claim.copy(),
                        dict(ip='192.0.2.1', claimed_mac='22', source_mac='bb', count=1)])
        result = self.make_extractor().extract(data)['aa']
        self.assertEqual(result.conflict, 0.5)

    def test_pure_poisoner_reply_ratio_is_one(self):
        result = self.make_extractor().extract(snapshot())['aa']
        self.assertEqual(result.arp_reply_ratio, 1.0)

    def test_balanced_reply_ratio_is_half(self):
        data = snapshot(devices={'aa': dict(bytes=1000, arp_requests=25, arp_replies=25)})
        result = self.make_extractor().extract(data)['aa']
        self.assertEqual(result.arp_reply_ratio, 0.5)

    def test_no_arp_ratio_unavailable(self):
        data = snapshot(devices={'aa': dict(bytes=1000, arp_requests=0, arp_replies=0)})
        result = self.make_extractor().extract(data)['aa']
        self.assertIsNone(result.arp_reply_ratio)
        self.assertIn('arp_reply_ratio_unavailable', result.missing_reasons)

    def test_incomplete_window_forces_ratio_none(self):
        result = self.make_extractor().extract(snapshot(incomplete=True))['aa']
        self.assertIsNone(result.arp_reply_ratio)

    def test_capture_quality_becomes_missing_memberships(self):
        for flag in ('incomplete', 'warming_up'):
            result = self.make_extractor().extract(snapshot(**{flag: True}))['aa']
            self.assertIsNone(result.conflict)
            self.assertIsNone(result.arp_frequency)
            self.assertIsNone(result.volume_deviation)
            self.assertIsNone(result.arp_reply_ratio)
            self.assertIsNone(infer(result).score)

    def test_reputation_provider_unknown_is_missing(self):
        data = self.make_extractor(reputation=Reputation.UNKNOWN).extract(snapshot())['aa']
        self.assertIsNone(data.reputation)

    def test_replacing_provider_changes_classification(self):
        for reputation, expected in [(Reputation.NEW, 'suspeito'),
                                      (Reputation.KNOWN, 'desconhecido')]:
            engine = FuzzyRiskStrategy(FixedReputation({'aa': reputation}), FixedBaseline({}))
            self.assertEqual(engine.classify(snapshot())['aa'].classification, expected)
