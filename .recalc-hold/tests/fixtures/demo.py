"""Gera PCAP sintético determinístico; nunca transmite pacotes.

Ping antes do ataque; depois, 10 ARP replies/s do Atacante reivindicam o Gateway.
A ausência de respostas ICMP durante essa fase é apenas uma representação
sintética. Não constitui prova de falha de conectividade em uma VM real.
"""
from scapy.all import Ether, ARP, IP, ICMP, wrpcap

ATTACKER = '02:00:00:00:00:30'
VICTIM = '02:00:00:00:00:20'
GATEWAY = '02:00:00:00:00:10'
GATEWAY_IP = '192.0.2.1'
VICTIM_IP = '192.0.2.2'
EPOCH = 1700000000


def packets(gateway_claim=True, gateway_ip=GATEWAY_IP, victim_ip=VICTIM_IP):
    result = []

    def add(packet, elapsed):
        packet.time = EPOCH + elapsed
        result.append(packet)

    for second in (0, 1):
        add(Ether(src=VICTIM, dst=GATEWAY) /
            IP(src=victim_ip, dst=gateway_ip, id=second + 1) /
            ICMP(type=8, id=7, seq=second), second)
        add(Ether(src=GATEWAY, dst=VICTIM) /
            IP(src=gateway_ip, dst=victim_ip, id=second + 1) /
            ICMP(type=0, id=7, seq=second), second + 0.05)
    if gateway_claim:
        add(Ether(src=GATEWAY, dst=VICTIM) /
            ARP(op=2, hwsrc=GATEWAY, psrc=gateway_ip,
                hwdst=VICTIM, pdst=victim_ip), 3.05)
    for index in range(100):
        add(Ether(src=ATTACKER, dst=VICTIM) /
            ARP(op=2, hwsrc=ATTACKER, psrc=gateway_ip,
                hwdst=VICTIM, pdst=victim_ip), 2 + index / 10)
    return sorted(result, key=lambda packet: packet.time)


def write_fixtures(directory):
    for name, claim in [('demo_gateway_claim.pcap', True),
                        ('demo_no_gateway_claim.pcap', False)]:
        wrpcap(str(directory / name), packets(claim))
