import unittest
from threading import Event
from unittest.mock import patch, MagicMock
from scapy.all import Ether, ARP, IP, ICMP, IPv6, Raw
from netsentinel.capture.config import CaptureConfig
from netsentinel.capture.normalizer import normalize
from netsentinel.capture.window import CLAIMED_IPS_LIMIT, ObservationWindow
from netsentinel.capture.service import CaptureService
from netsentinel.capture.scapy_source import ScapySource

A = '02:00:00:00:00:01'
B = '02:00:00:00:00:02'
C = '02:00:00:00:00:03'


def arp(mac=A, ip='192.0.2.1', op=2, claimed=None):
    # Serialização reproduz os campos resolvidos que chegam pela captura real.
    return Ether(bytes(Ether(src=mac, dst=B) / ARP(
        op=op, hwsrc=claimed or mac, psrc=ip, hwdst=B, pdst='192.0.2.2')))


class CaptureTests(unittest.TestCase):
    def test_elapsed_duration_and_warmup_in_silence(self):
        clock = [100.0]
        published = []
        service = CaptureService(CaptureConfig('lab0', 10, 10, True),
                                 published.append, clock=lambda: clock[0])
        service.ingest(arp())
        clock[0] = 104.0
        service.emit()
        self.assertEqual(published[-1]['observed_seconds'], 4)
        self.assertTrue(published[-1]['warming_up'])
        clock[0] = 112.0
        service.emit()
        self.assertEqual(published[-1]['observed_seconds'], 10)
        self.assertFalse(published[-1]['warming_up'])
        self.assertEqual(published[-1]['observations'], 0)

    def test_preserves_claim_and_actual_source(self):
        obs = normalize(arp(claimed=C))
        self.assertEqual((obs.src_mac, obs.arp_sender_mac), (A, C))

    def test_ip_volume(self):
        packet = Ether(src=A, dst=B) / IP(src='192.0.2.1', dst='192.0.2.2') / ICMP()
        obs = normalize(packet)
        self.assertEqual(obs.size_bytes, len(packet))
        self.assertEqual(obs.src_ip, '192.0.2.1')
        self.assertEqual(obs.protocol, 'IPv4')

    def test_ipv6(self):
        obs = normalize(Ether(src=A, dst=B) / IPv6(src='::1', dst='::2'))
        self.assertEqual(obs.protocol, 'IPv6')

    def test_non_ethernet_ignored(self):
        self.assertIsNone(normalize(Raw(b'anything')))

    def test_conflicting_claims_not_trusted(self):
        window = ObservationWindow(10, 10)
        window.add(normalize(arp()), 0)
        window.add(normalize(arp(mac=C)), 1)
        snapshot = window.snapshot(1)
        self.assertEqual(len(snapshot['arp_claims']), 2)
        self.assertNotIn('trusted_mac', snapshot)

    def test_probe_not_claim(self):
        window = ObservationWindow(10, 10)
        window.add(normalize(arp(ip='0.0.0.0', op=1)), 0)
        result = window.snapshot(0)
        self.assertEqual(result['arp_claims'], [])
        self.assertEqual(result['devices'][A]['arp_requests'], 1)

    def test_expiry_in_silence(self):
        window = ObservationWindow(10, 10)
        window.add(normalize(arp()), 0)
        self.assertEqual(window.snapshot(9)['observations'], 1)
        self.assertEqual(window.snapshot(10)['observations'], 0)
        self.assertEqual(window.snapshot(10)['devices'], {})

    def test_capacity_signals_incomplete_until_eviction_expires(self):
        window = ObservationWindow(10, 1)
        window.add(normalize(arp()), 0)
        window.add(normalize(arp(mac=C)), 1)
        self.assertTrue(window.snapshot(1)['incomplete'])
        self.assertEqual(window.snapshot(1)['evicted_total'], 1)
        self.assertFalse(window.snapshot(10)['incomplete'])
        self.assertEqual(window.snapshot(10)['observations'], 1)

    def test_counts_and_links(self):
        window = ObservationWindow(10, 10)
        packet = arp()
        for i in range(3):
            window.add(normalize(packet), i)
        snap = window.snapshot(3)
        self.assertEqual(snap['devices'][A]['bytes'], 3 * len(packet))
        self.assertEqual(snap['devices'][A]['arp_replies'], 3)
        self.assertEqual(snap['links'][0]['packets'], 3)

    def test_snapshot_counts_protocols(self):
        window = ObservationWindow(10, 10)
        window.add(normalize(arp()), 0)
        window.add(normalize(arp()), 1)
        window.add(normalize(Ether(src=A, dst=B) / IP(src='192.0.2.1', dst='192.0.2.2') / ICMP()), 2)
        window.add(normalize(Ether(src=A, dst=B) / IPv6(src='::1', dst='::2')), 3)
        window.add(normalize(Ether(src=A, dst=B)), 4)
        self.assertEqual(window.snapshot(4)['devices'][A]['protocols'], {
            'ARP': 2, 'IPv4': 1, 'IPv6': 1, 'OTHER': 1,
        })

    def test_snapshot_lists_distinct_claimed_ips_in_first_seen_order(self):
        window = ObservationWindow(10, 10)
        window.add(normalize(Ether(src=A, dst=B) / IP(src='192.0.2.10', dst='192.0.2.2') / ICMP()), 0)
        window.add(normalize(Ether(src=A, dst=B) / IP(src='192.0.2.20', dst='192.0.2.2') / ICMP()), 1)
        window.add(normalize(Ether(src=A, dst=B) / IP(src='192.0.2.10', dst='192.0.2.2') / ICMP()), 2)
        device = window.snapshot(2)['devices'][A]
        self.assertEqual(device['claimed_ips'], ['192.0.2.10', '192.0.2.20'])
        self.assertEqual(device['claimed_ips_total'], 2)

    def test_snapshot_caps_claimed_ips_and_keeps_total(self):
        window = ObservationWindow(20, 20)
        for index in range(12):
            ip = f'192.0.2.{index + 1}'
            window.add(normalize(Ether(src=A, dst=B) / IP(src=ip, dst='192.0.2.254') / ICMP()), index)
        device = window.snapshot(12)['devices'][A]
        self.assertEqual(device['claimed_ips'], [f'192.0.2.{n}' for n in range(1, 11)])
        self.assertEqual(device['claimed_ips_total'], 12)
        self.assertEqual(CLAIMED_IPS_LIMIT, 10)
        self.assertEqual(len(device['claimed_ips']), CLAIMED_IPS_LIMIT)

    def test_snapshot_device_without_ip_has_empty_claimed_list(self):
        window = ObservationWindow(10, 10)
        window.add(normalize(Ether(src=A, dst=B)), 0)
        device = window.snapshot(0)['devices'][A]
        self.assertEqual(device['claimed_ips'], [])
        self.assertEqual(device['claimed_ips_total'], 0)

    def test_invalid_configuration(self):
        for seconds in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                CaptureConfig('eth0', seconds, 10, True)
        with self.assertRaises(ValueError):
            CaptureConfig('eth0', 10, 10, False)
        with self.assertRaises(ValueError):
            CaptureConfig('any', 10, 10, True)

    def test_publish_and_close_on_stop(self):
        source = MagicMock()
        source.__enter__.return_value = source
        stop = Event()
        source.poll.side_effect = lambda callback: (callback(arp()), stop.set())
        published = []
        service = CaptureService(CaptureConfig('lab0', 10, 10, True),
                                 published.append, clock=lambda: 0,
                                 source_factory=lambda _: source)
        service.run(stop)
        self.assertEqual(published[-1]['observations'], 1)
        source.__exit__.assert_called_once()

    def test_socket_closed_on_consumer_error(self):
        source = MagicMock()
        source.__enter__.return_value = source
        def broken(_):
            raise RuntimeError('consumer failure')
        service = CaptureService(CaptureConfig('lab0', 10, 10, True), broken,
                                 source_factory=lambda _: source)
        with self.assertRaises(RuntimeError):
            service.run(Event())
        source.__exit__.assert_called_once()

    @patch('netsentinel.capture.scapy_source.sniff')
    @patch('netsentinel.capture.scapy_source.conf')
    @patch('netsentinel.capture.scapy_source.get_if_list', return_value=['lab0'])
    def test_promiscuous_persistent_socket(self, interfaces, conf, sniff):
        callback = MagicMock()
        with ScapySource('lab0') as source:
            source.poll(callback)
            source.poll(callback)
        conf.L2listen.assert_called_once_with(iface='lab0', promisc=True)
        self.assertEqual(sniff.call_count, 2)
        self.assertFalse(sniff.call_args.kwargs['store'])
        self.assertTrue(sniff.call_args.kwargs['promisc'])
        conf.L2listen.return_value.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
