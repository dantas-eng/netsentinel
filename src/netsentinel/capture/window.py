"""Janela móvel (agora - duração, agora], com memória limitada.

O relógio monotônico de ingestão evita saltos de NTP. O consumidor recebe
contagens brutas: reputação, baseline e intensidade de conflito pertencem à análise.
"""
from collections import Counter, deque


class ObservationWindow:
    def __init__(self, seconds, capacity):
        self.seconds = seconds
        self.capacity = capacity
        self.items = deque()
        self.evicted_total = 0
        self.last_evicted_at = None

    def _expire(self, now):
        while self.items and self.items[0][0] <= now - self.seconds:
            self.items.popleft()

    def add(self, observation, now):
        self._expire(now)
        if len(self.items) == self.capacity:
            evicted_at, _ = self.items.popleft()
            self.last_evicted_at = evicted_at
            self.evicted_total += 1
        self.items.append((now, observation))

    def snapshot(self, now):
        self._expire(now)
        devices, claims, links = {}, Counter(), Counter()
        for _, obs in self.items:
            # Ethernet identifica a origem observada; ARP pode alegar outro MAC.
            device = devices.setdefault(obs.src_mac, dict(
                packets=0, bytes=0, arp_requests=0, arp_replies=0,
                first_timestamp=obs.timestamp, last_timestamp=obs.timestamp))
            device["packets"] += 1
            device["bytes"] += obs.size_bytes
            device["first_timestamp"] = min(device["first_timestamp"], obs.timestamp)
            device["last_timestamp"] = max(device["last_timestamp"], obs.timestamp)
            links[(obs.src_mac, obs.dst_mac)] += 1
            if obs.arp_operation in (1, 2):
                device["arp_requests" if obs.arp_operation == 1 else "arp_replies"] += 1
                # Probe 0.0.0.0 não afirma propriedade de endereço IPv4.
                if obs.arp_sender_ip != "0.0.0.0":
                    claims[(obs.arp_sender_ip, obs.arp_sender_mac, obs.src_mac)] += 1
        return dict(window_seconds=self.seconds, observations=len(self.items),
                    incomplete=self.last_evicted_at is not None and
                    self.last_evicted_at > now - self.seconds,
                    evicted_total=self.evicted_total, devices=devices,
                    arp_claims=[dict(ip=ip, claimed_mac=mac, source_mac=src, count=n)
                                for (ip, mac, src), n in sorted(claims.items())],
                    links=[dict(source=src, target=dst, packets=n)
                           for (src, dst), n in sorted(links.items())])
