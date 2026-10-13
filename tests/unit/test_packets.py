import struct
import unittest
from netsentinel.packets.dissect import MAX_FRAME_BYTES, dissect, verdict

TRUSTED = {'10.77.0.1': '02:00:00:00:00:10', '10.77.0.20': '02:00:00:00:00:20'}


def mac(text):
    return bytes(int(part, 16) for part in text.split(':'))


def ip(text):
    return bytes(int(part) for part in text.split('.'))


def arp(op, sha, spa, tha, tpa, dst='02:00:00:00:00:20', src=None, vlan=None, pad=True, hwtype=1):
    eth = mac(dst) + mac(src or sha)
    if vlan is not None:
        eth += struct.pack('!HH', 0x8100, vlan)
    body = struct.pack('!HHBBH', hwtype, 0x0800, 6, 4, op) + mac(sha) + ip(spa) + mac(tha) + ip(tpa)
    frame = eth + b'\x08\x06' + body
    return frame + b'\x00' * (60 - len(frame)) if pad else frame


REPLY = arp(2, '02:00:00:00:00:30', '10.77.0.1', '02:00:00:00:00:20', '10.77.0.20')
REQUEST = arp(1, '02:00:00:00:00:20', '10.77.0.20', '00:00:00:00:00:00', '10.77.0.1',
              dst='ff:ff:ff:ff:ff:ff')


def field(packet, layer, name):
    for item in packet['layers']:
        if item['name'] == layer:
            return next(f for f in item['fields'] if f['name'] == name)
    raise AssertionError(layer)


class DissectTests(unittest.TestCase):
    def test_reply_layers_and_offsets(self):
        packet = dissect(REPLY)
        self.assertEqual([layer['name'] for layer in packet['layers']],
                         ['Ethernet II', 'Address Resolution Protocol (reply)', 'Preenchimento'])
        sender = field(packet, 'Address Resolution Protocol (reply)', 'IP do remetente')
        self.assertEqual((sender['value'], sender['start'], sender['end']), ('10.77.0.1', 28, 32))
        self.assertEqual(packet['length'], 60)
        self.assertEqual((packet['opcode'], packet['sender_mac'], packet['eth_src']),
                         (2, '02:00:00:00:00:30', '02:00:00:00:00:30'))
        self.assertEqual(packet['summary'], '10.77.0.1 está em 02:00:00:00:00:30')

    def test_request_summary(self):
        packet = dissect(REQUEST)
        self.assertEqual(packet['summary'], 'Quem tem 10.77.0.1? Diga a 10.77.0.20')
        self.assertEqual(packet['eth_dst'], 'ff:ff:ff:ff:ff:ff')

    def test_unpadded_frame_has_no_padding_layer(self):
        packet = dissect(arp(2, '02:00:00:00:00:10', '10.77.0.1', '02:00:00:00:00:20', '10.77.0.20', pad=False))
        self.assertEqual(len(packet['layers']), 2)
        self.assertEqual(packet['length'], 42)

    def test_vlan_tag_shifts_arp_offsets(self):
        packet = dissect(arp(2, '02:00:00:00:00:30', '10.77.0.1', '02:00:00:00:00:20', '10.77.0.20', vlan=7))
        self.assertEqual(packet['layers'][1]['name'], '802.1Q')
        self.assertEqual(field(packet, '802.1Q', 'VLAN')['value'], '7')
        sender = field(packet, 'Address Resolution Protocol (reply)', 'IP do remetente')
        self.assertEqual((sender['start'], sender['end']), (32, 36))

    def test_short_frame_raises(self):
        with self.assertRaises(ValueError):
            dissect(REPLY[:30])

    def test_wrong_ethertype_raises(self):
        with self.assertRaises(ValueError):
            dissect(REPLY[:12] + b'\x08\x00' + REPLY[14:])

    def test_non_ethernet_arp_raises(self):
        with self.assertRaises(ValueError):
            dissect(arp(2, '02:00:00:00:00:30', '10.77.0.1', '02:00:00:00:00:20', '10.77.0.20', hwtype=6))

    def test_max_frame_bytes(self):
        self.assertEqual(MAX_FRAME_BYTES, 128)


class VerdictTests(unittest.TestCase):
    def test_spoofed_trusted_ip(self):
        result = verdict(dissect(REPLY), TRUSTED)
        self.assertEqual(result, dict(spoofed=True, expected_mac='02:00:00:00:00:10', reason='spoofed_trusted_ip'))

    def test_matches_inventory(self):
        self.assertEqual(verdict(dissect(REQUEST), TRUSTED)['reason'], 'matches_inventory')

    def test_ip_not_in_inventory(self):
        packet = dissect(arp(2, '02:00:00:00:00:30', '10.77.0.99', '02:00:00:00:00:20', '10.77.0.20'))
        self.assertEqual(verdict(packet, TRUSTED),
                         dict(spoofed=False, expected_mac=None, reason='ip_not_in_inventory'))

    def test_probe_is_never_spoofed(self):
        packet = dissect(arp(1, '02:00:00:00:00:30', '0.0.0.0', '00:00:00:00:00:00', '10.77.0.1',
                             dst='ff:ff:ff:ff:ff:ff'))
        self.assertEqual(verdict(packet, TRUSTED)['reason'], 'probe')
        self.assertFalse(verdict(packet, TRUSTED)['spoofed'])
