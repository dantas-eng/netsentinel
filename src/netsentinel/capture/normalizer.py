"""Descarta payload após extrair metadados Ethernet, ARP e IP."""
from scapy.layers.l2 import ARP, Ether
from scapy.layers.inet import IP
from scapy.layers.inet6 import IPv6
from netsentinel.domain.observation import Observation


def normalize(packet):
    if Ether not in packet:
        return None
    eth = packet[Ether]
    data = dict(timestamp=float(packet.time), src_mac=eth.src.lower(),
                dst_mac=eth.dst.lower(), size_bytes=len(packet), protocol="OTHER")
    if ARP in packet:
        arp = packet[ARP]
        # Não interpretar outros formatos de ARP como Ethernet/IPv4.
        if (arp.hwtype, arp.ptype, arp.hwlen, arp.plen) != (1, 0x0800, 6, 4):
            return Observation(**data)
        data.update(protocol="ARP", src_ip=arp.psrc, dst_ip=arp.pdst,
                    arp_operation=int(arp.op), arp_sender_mac=arp.hwsrc.lower(),
                    arp_sender_ip=arp.psrc)
    elif IP in packet:
        data.update(protocol="IPv4", src_ip=packet[IP].src, dst_ip=packet[IP].dst)
    elif IPv6 in packet:
        data.update(protocol="IPv6", src_ip=packet[IPv6].src, dst_ip=packet[IPv6].dst)
    return Observation(**data)
