"""Integração real com Scapy/PCAP, sem interface de rede ou privilégios."""
import tempfile
import unittest
from pathlib import Path
from scapy.all import Ether, IP, ICMP, ARP, sniff, wrpcap
from netsentinel.capture.config import CaptureConfig
from netsentinel.capture.service import CaptureService


class OfflineIntegration(unittest.TestCase):
    def test_pcap_through_service(self):
        packets = [
            Ether(src='02:00:00:00:00:01', dst='02:00:00:00:00:02') /
            IP(src='192.0.2.1', dst='192.0.2.2') / ICMP(),
            Ether(src='02:00:00:00:00:03', dst='02:00:00:00:00:02') /
            ARP(op=2, hwsrc='02:00:00:00:00:03', psrc='192.0.2.1',
                hwdst='02:00:00:00:00:02', pdst='192.0.2.2')]
        result = []
        service = CaptureService(CaptureConfig('unused', 10, 100, True),
                                 result.append, clock=lambda: 0)
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'synthetic.pcap')
            wrpcap(path, packets)
            sniff(offline=path, store=False, prn=service.ingest)
        service.emit()
        self.assertEqual(result[0]['observations'], 2)
        self.assertEqual(result[0]['malformed_total'], 0)
        self.assertEqual(result[0]['arp_claims'][0]['ip'], '192.0.2.1')
