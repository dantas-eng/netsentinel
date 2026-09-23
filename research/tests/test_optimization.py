"""Validação offline da extensão; nenhuma interface de rede é aberta."""
import hashlib
import io
from copy import deepcopy
import json
import random
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import numpy as np

from netsentinel.analysis.fuzzy.engine import infer
from netsentinel.analysis.models import RiskInputs
from netsentinel.optimization.classifier import (
    ParameterizedFuzzyRiskStrategy, Parameters, memberships, scores,
)
from netsentinel.optimization.dataset import Context, TARGET, inputs_of, load, replay
from netsentinel.optimization.experiment import BOUNDS, metrics, nondominated, optimize
from netsentinel.analysis.contracts import Reputation
from netsentinel.optimization.diagnostics import diagnose, validate


class ClassifierTests(unittest.TestCase):
    def setUp(self):
        context = Context(Reputation.NEW, None)
        self.strategy = ParameterizedFuzzyRiskStrategy(context, context)

    def test_manual_equivalence_random_and_missing(self):
        rng = random.Random(10)
        examples = [RiskInputs(rng.choice([None, 0., .5, rng.random()]),
                              rng.choice([None, 0., 5., rng.random()*20]),
                              rng.choice([None, 'new', 'known']),
                              rng.choice([None, 0., 1., rng.random()*4]),
                              rng.choice([None, 0., .5, 1., rng.random()])) for _ in range(300)]
        for inputs, score in zip(examples, scores(examples, Parameters())):
            expected = infer(inputs)
            actual = self.strategy.infer(inputs)
            self.assertEqual(expected.classification, actual.classification)
            self.assertEqual(expected.rule_strengths, actual.rule_strengths)
            if expected.score is None:
                self.assertTrue(np.isnan(score))
                self.assertIsNone(actual.score)
            else:
                self.assertAlmostEqual(expected.score, score, places=9)
                self.assertAlmostEqual(expected.score, actual.score, places=9)

    def test_missing_is_zero_not_low(self):
        inputs = RiskInputs(0., 10., 'new', None)
        result = self.strategy.infer(inputs)
        self.assertEqual(result.memberships['deviation'], {'low': 0., 'high': 0.})
        self.assertEqual(result.rule_strengths['R4'], 0)
        self.assertEqual(result.memberships['ratio'], {'low': 0., 'high': 0.})
        for ratio, high in ((0., 0.), (.5, 0.), (.75, .5), (1., 1.)):
            value = self.strategy.infer(RiskInputs(0., 0., 'new', 0., ratio))
            self.assertEqual(value.memberships['ratio']['high'], high)
        ratio_only = self.strategy.infer(RiskInputs(0., 0., 'new', 0., 1.))
        self.assertEqual(ratio_only.rule_strengths['R2'], 1.)
        self.assertGreaterEqual(result.score, 65)

    def test_conflict_independent_of_unknown_and_baseline(self):
        self.assertGreaterEqual(self.strategy.infer(RiskInputs(.5, None, None, None)).score, 65)

    def test_abstention_emerges_from_rules(self):
        self.assertEqual(self.strategy.infer(RiskInputs(0., None, None, None)).reason,
                         'no_rule_activated')

    def test_saturation_and_configurable_threshold(self):
        inputs = RiskInputs(.5, 1., 'new', None)
        self.assertEqual(memberships(inputs, Parameters(conflict=.5))['conflict']['high'], 1.)
        context = Context(Reputation.NEW, None)
        strategy = ParameterizedFuzzyRiskStrategy(context, context, Parameters(upper=90))
        self.assertEqual(strategy.infer(RiskInputs(1., 10., 'new', None)).classification,
                         'desconhecido')

    def test_invalid_parameters(self):
        for values in ({'conflict': 0}, {'frequency': float('nan')}, {'upper': 30}):
            with self.assertRaises(ValueError):
                Parameters(**values)


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = load('research/results/dataset')

    def test_counts_splits_groups_and_no_duplicate_pcaps(self):
        self.assertEqual(len(self.records), 600)

        self.assertEqual(sum(r['label'] for r in self.records), 180)
        self.assertEqual(Counter(r['split'] for r in self.records),
                         {'train': 360, 'validation': 120, 'test': 120})
        self.assertEqual(len({r['id'] for r in self.records}), 600)
        self.assertEqual(len({r['pcap_sha256'] for r in self.records}), 600)
        for split in ('train', 'validation', 'test'):
            subset = [r for r in self.records if r['split'] == split]
            self.assertEqual(sum(r['label'] for r in subset)/len(subset), .3)

    def test_pcap_replay_integrity_and_features(self):
        for record in self.records[::37]:
            content, features = replay(record['config'])
            self.assertEqual(hashlib.sha256(content).hexdigest(), record['pcap_sha256'])
            self.assertEqual(features.arp_frequency, record['config']['arp_count']/8)
            self.assertEqual(features.arp_reply_ratio,
                             record['config']['arp_reply_count']/record['config']['arp_count'])
            self.assertEqual(features.conflict, .5 if record['config']['gateway_claim'] else 0)

    def test_new_attacker_no_baseline_end_to_end(self):
        _, features = replay({'reputation': 'new', 'baseline_bps': None, 'arp_count': 80, 'arp_reply_count': 60,
                              'gateway_claim': False, 'payload_count': 2, 'payload_size': 64})
        self.assertIsNone(features.volume_deviation)
        self.assertGreaterEqual(scores([features], Parameters())[0], 65)

    def test_real_requests_and_replies_survive_pcap(self):
        config = {'reputation': 'known', 'baseline_bps': 200, 'arp_count': 10,
                  'arp_reply_count': 4, 'gateway_claim': False,
                  'payload_count': 2, 'payload_size': 64}
        content, features = replay(config)
        from scapy.all import ARP, Ether, rdpcap
        packets = [p for p in rdpcap(io.BytesIO(content)) if ARP in p and p[Ether].src == TARGET]
        self.assertEqual(Counter(int(p[ARP].op) for p in packets), {1: 6, 2: 4})
        self.assertEqual(features.arp_reply_ratio, .4)
        self.assertEqual(features.arp_frequency, 1.25)
        for packet in packets:
            if packet[ARP].op == 1:
                self.assertEqual(packet[Ether].dst, 'ff:ff:ff:ff:ff:ff')
                self.assertEqual(packet[ARP].hwdst, '00:00:00:00:00:00')
                self.assertEqual(packet[ARP].psrc, '192.0.2.3')
                self.assertEqual(packet[ARP].pdst, '192.0.2.2')

    def test_ratio_varies_in_every_family_and_both_labels(self):
        for family in {r['family'] for r in self.records}:
            rows = [r for r in self.records if r['family'] == family]
            self.assertGreater(len({r['inputs']['arp_reply_ratio'] for r in rows}), 1)
            self.assertTrue(any(r['config']['arp_reply_count'] < r['config']['arp_count']
                                for r in rows))
        for label in (0, 1):
            ratios = [r['inputs']['arp_reply_ratio'] for r in self.records if r['label'] == label]
            self.assertTrue(any(x <= .5 for x in ratios))
            self.assertTrue(any(.5 < x < 1 for x in ratios))

    def test_training_sensitivity_and_honest_rule_coverage(self):
        result = diagnose(self.records)
        validate(result)
        for values in result['training_one_gene_at_a_time'].values():
            self.assertGreater(values['binary_decision_changes'], 0)
        self.assertGreater(result['training_rule_activation']['R5'], 0)
        self.assertEqual(result['training_rule_activation']['R4'], 0)
        self.assertTrue(all(r['inputs']['volume_deviation'] is None
                            for r in self.records if r['inputs']['reputation'] == 'new'))

    def test_gate_rejects_constant_ratio_even_in_version_two(self):
        rows = deepcopy(self.records)
        for row in rows:
            row['inputs']['arp_reply_ratio'] = 1.
            row['config']['arp_reply_count'] = row['config']['arp_count']
        with self.assertRaisesRegex(ValueError, 'Corpus degenerado'):
            validate(diagnose(rows))

    def test_strategy_contract(self):
        context = Context(Reputation.NEW, None)
        strategy = ParameterizedFuzzyRiskStrategy(context, context)
        snapshot = {'devices': {TARGET: {'bytes': 100, 'arp_requests': 0, 'arp_replies': 80}},
                    'arp_claims': [], 'observed_seconds': 8,
                    'warming_up': False, 'incomplete': False}
        self.assertGreaterEqual(strategy.classify(snapshot)[TARGET].score, 65)


class ExperimentTests(unittest.TestCase):
    def test_abstentions_stay_in_denominator(self):
        m = metrics([1, 1, 0, 0], [80, np.nan, 80, 0], 65)
        self.assertEqual((m['recall'], m['fpr'], m['f1'], m['abstentions']), (.5, .5, .5, 1))
        self.assertEqual(metrics([0], [0], 65)['precision'], 0)

    def test_empirical_front_dominance(self):
        points = [{'recall': .8, 'fpr': .1}, {'recall': .7, 'fpr': .2},
                  {'recall': 1., 'fpr': .3}]
        self.assertEqual(nondominated(points), [points[0], points[2]])

    def test_seed_reproducibility_and_bounds(self):
        examples = [RiskInputs(.5, 10., 'new', None), RiskInputs(0., .1, 'known', 0.)]
        data = (examples, [1, 0])
        with patch('netsentinel.optimization.experiment.GENERATIONS', 2):
            for method in ('ga', 'nsga2'):
                first = optimize(method, 7, data, data)
                self.assertEqual(first, optimize(method, 7, data, data))
                for candidate in first[2]:
                    for value, (low, high) in zip(candidate['genes'], BOUNDS):
                        self.assertTrue(low <= value <= high)

    def test_complete_results_when_available(self):
        path = Path('research/results/results.json')
        if not path.exists():
            self.skipTest('Experimento completo ainda em execução.')
        data = json.loads(path.read_text())
        self.assertEqual(len(data['runs']), 40)
        records = [r for r in load('research/results/dataset') if r['split'] == 'test']
        inputs, labels = inputs_of(records), [r['label'] for r in records]
        for run in data['runs']:
            actual = metrics(labels, scores(inputs, Parameters.genes(run['genes'])), run['genes'][3])
            self.assertEqual(actual, run['test'])
        manual = metrics(labels, [infer(x).score for x in inputs], 65)
        self.assertEqual(manual, data['baseline_test'])
        for method in ('ga', 'nsga2'):
            runs = [r for r in data['runs'] if r['method'] == method]
            self.assertEqual([r['seed'] for r in runs], list(range(20)))
            self.assertAlmostEqual(np.std([r['test']['f1'] for r in runs], ddof=1),
                                   data['summary_test'][method]['f1']['sample_sd'])
