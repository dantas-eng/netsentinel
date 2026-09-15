"""Fonte cloud em memória: sem Scapy, sockets raw ou comunicação com o laboratório."""
from dataclasses import dataclass
from time import monotonic, time
from uuid import uuid4


@dataclass(frozen=True)
class SyntheticIdentity:
    gateway_mac: str = '02:00:00:00:00:10'
    victim_mac: str = '02:00:00:00:00:20'
    attacker_mac: str = '02:00:00:00:00:30'
    sensor_internal_mac: str = '02:00:00:00:00:40'
    gateway_ip: str = '192.0.2.1'
    victim_ip: str = '192.0.2.2'
    attacker_ip: str = '192.0.2.3'
    sensor_internal_ip: str = '192.0.2.4'

    def trusted_bindings(self):
        return {self.gateway_ip: self.gateway_mac, self.victim_ip: self.victim_mac,
                self.attacker_ip: self.attacker_mac, self.sensor_internal_ip: self.sensor_internal_mac}


class SyntheticMitigation:
    def __init__(self, identity, clock=monotonic):
        self.identity, self.clock = identity, clock
        self.applied_at = None
        self.run_id = 'synthetic-' + uuid4().hex

    def apply(self, attacker_mac):
        if attacker_mac != self.identity.attacker_mac:
            raise ValueError('MAC fora da demonstração sintética.')
        if self.applied_at is None:
            self.applied_at = self.clock()
        return self.status()

    def status(self):
        active = self.applied_at is not None
        n = int((self.clock() - self.applied_at) * 10) if active else 0
        return dict(simulated=True, timestamp=time(), run_id=self.run_id,
                    attacker_mac=self.identity.attacker_mac, gateway_ip=self.identity.gateway_ip,
                    mitigated=active, blocked=active, arp_static_correct=active,
                    counters={name: dict(packets=n if name != 'passed' else 0, bytes=0)
                              for name in ('seen', 'dropped', 'passed')})


class SyntheticSource:
    def __init__(self, clock=monotonic):
        self.clock, self.started = clock, clock()
        self.run_id = uuid4().hex
        self.identity = SyntheticIdentity()

    def snapshot(self):
        now = self.clock()
        elapsed = max(0, now - self.started)
        duration = min(8.0, elapsed)
        devices = {}
        for index, mac in enumerate((self.identity.gateway_mac, self.identity.victim_mac,
                                      self.identity.sensor_internal_mac)):
            devices[mac] = dict(bytes=int((index + 1) * 400 * duration), packets=int(10 * duration),
                                arp_requests=0, arp_replies=0, first_timestamp=time(), last_timestamp=time())
        # Após 60 s, tráfego sintético anômalo. Todos os eventos permanecem marcados.
        attacking = elapsed >= 60
        claims = []
        if attacking:
            devices[self.identity.attacker_mac] = dict(bytes=int(420 * duration), packets=int(10 * duration),
                                                       arp_requests=0, arp_replies=int(10 * duration))
            claims.append(dict(ip=self.identity.gateway_ip, claimed_mac=self.identity.attacker_mac,
                               source_mac=self.identity.attacker_mac, count=int(10 * duration)))
        return dict(timestamp=time(), source='synthetic', interface='synthetic',
                    window_seconds=8, observed_seconds=duration, warming_up=elapsed < 8,
                    incomplete=False, capture_run_id=self.run_id, window_end_monotonic=now,
                    window_start_monotonic=now-duration, devices=devices, arp_claims=claims,
                    links=[dict(source=self.identity.victim_mac, target=self.identity.gateway_mac,
                                packets=int(10*duration))], observations=sum(d['packets'] for d in devices.values()))
