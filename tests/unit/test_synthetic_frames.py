import unittest
from netsentinel.packets.dissect import dissect, verdict
from netsentinel.services.synthetic import SyntheticIdentity, SyntheticSource


def frames_at(seconds):
    clock = [1000.0]
    source = SyntheticSource(clock=lambda: clock[0])
    clock[0] += seconds
    return [verdict(dissect(f['raw']), SyntheticIdentity().trusted_bindings()) | dissect(f['raw'])
            for f in source.snapshot()['arp_frames']]


class SyntheticFrameTests(unittest.TestCase):
    def test_only_legitimate_frames_before_attack(self):
        frames = frames_at(30)
        self.assertTrue(frames)
        self.assertFalse(any(f['spoofed'] for f in frames))

    def test_attacker_claims_gateway_after_60_seconds(self):
        spoofed = [f for f in frames_at(61) if f['spoofed']]
        self.assertTrue(spoofed)
        self.assertEqual({(f['sender_mac'], f['sender_ip']) for f in spoofed},
                         {('02:00:00:00:00:30', '192.0.2.1')})

    def test_intruder_claims_victim_after_90_seconds(self):
        claims = {(f['sender_mac'], f['sender_ip']) for f in frames_at(91) if f['spoofed']}
        self.assertIn(('02:00:00:00:00:50', '192.0.2.2'), claims)

    def test_at_most_ten_frames_per_snapshot(self):
        self.assertLessEqual(len(frames_at(200)), 10)
