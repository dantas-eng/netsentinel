"""Pipeline local no Sensor: captura -> fuzzy -> decisão -> agente da Vítima.

Este comando é o executor da demo antes do backend/dashboard. Não abre porta
HTTP no Sensor. O futuro backend reutilizará Strategy e controller de eventos.
"""
import argparse
from dataclasses import asdict
import json
from threading import Event
import signal
import time
from netsentinel.analysis.contracts import Reputation
from netsentinel.analysis.fuzzy import FuzzyRiskStrategy
from netsentinel.security.config import load_config
from netsentinel.security.system import LinuxSystem, preflight
from netsentinel.security.strategy import VictimAgentMitigationStrategy, AgentFailure
from netsentinel.security.evidence import verify_interval


class LabReputation:
    """Inventário explícito da demo; nunca transforma primeiro avistamento em KNOWN."""
    def __init__(self, config):
        self.known = {config.gateway_mac, config.victim_mac, config.sensor_internal_mac}

    def get_reputation(self, mac):
        return Reputation.KNOWN if mac in self.known else Reputation.NEW


class NoHistoricalBaseline:
    def get_baseline_bps(self, mac):
        return None


class SecurityDemo:
    def __init__(self, config, classifier, mitigation, publish):
        self.config, self.classifier = config, classifier
        self.mitigation, self.publish = mitigation, publish
        self.applied = False
        self.qualifying_mac = None
        self.qualifying_count = 0

    def consume(self, snapshot):
        results = self.classifier.classify(snapshot)
        result = results.get(self.config.attacker_mac)
        # Score sozinho não identifica autoria. Vincular origem à alegação falsa
        # sobre o Gateway conhecido; apenas o Atacante configurado é elegível.
        false_claim = any(c['source_mac'] == self.config.attacker_mac and
                          c['ip'] == self.config.gateway_ip and
                          c['claimed_mac'] != self.config.gateway_mac
                          for c in snapshot['arp_claims'])
        self.publish(dict(event='risk_evaluated', timestamp=snapshot['timestamp'],
                          attacker=asdict(result) if result else None,
                          devices={mac: asdict(value) for mac, value in results.items()},
                          false_gateway_claim=false_claim))
        try:
            if self.applied:
                status = self.mitigation.status()
                self.publish(dict(event='mitigation_status', evidence=status))
                self.applied = status.get('mitigated') is True
            if not self.applied:
                qualifies = false_claim and result is not None and result.score is not None and result.score >= 65
                if not qualifies:
                    # Uma avaliação negativa rompe a sequência, inclusive score nulo.
                    self.qualifying_mac, self.qualifying_count = None, 0
                else:
                    mac = self.config.attacker_mac
                    self.qualifying_count = min(2, self.qualifying_count + 1) if self.qualifying_mac == mac else 1
                    self.qualifying_mac = mac
                    # ADR 0007: avaliações consecutivas, não duas janelas independentes.
                    if self.qualifying_count >= 2:
                        status = self.mitigation.apply(mac)
                        self.applied = True
                        self.qualifying_mac, self.qualifying_count = None, 0
                        self.publish(dict(event='mitigation_applied', evidence=status))
        except AgentFailure:
            self.publish(dict(event='mitigation_error', retry_on_next_snapshot=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('monitor', 'preflight', 'verify'))
    parser.add_argument('--config', required=True)
    parser.add_argument('--max-observations', type=int)
    parser.add_argument('--evidence-seconds', type=float, default=5)
    args = parser.parse_args()
    config = load_config(args.config)
    preflight(config, 'sensor', LinuxSystem())
    if args.action == 'preflight':
        print('Condições locais verificadas. Confirmar no VirtualBox a ausência de bridge/NAT/ICS.')
        return
    strategy = VictimAgentMitigationStrategy(config)
    if args.action == 'verify':
        if not 0 < args.evidence_seconds <= 30:
            parser.error('Intervalo de evidência deve estar entre 0 e 30 segundos.')
        before = strategy.status()
        time.sleep(args.evidence_seconds)
        after = strategy.status()
        result = verify_interval(before, after)
        print(json.dumps(dict(before=before, after=after, result=result), ensure_ascii=False))
        raise SystemExit(0 if result['verified'] else 1)
    if args.max_observations is None:
        parser.error('--max-observations é obrigatório para monitor.')
    from netsentinel.capture.config import CaptureConfig
    from netsentinel.capture.service import CaptureService
    stop = Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    classifier = FuzzyRiskStrategy(LabReputation(config), NoHistoricalBaseline())
    demo = SecurityDemo(config, classifier, strategy,
                        lambda value: print(json.dumps(value, ensure_ascii=False), flush=True))
    CaptureService(CaptureConfig(config.interface, 8, args.max_observations, True),
                   demo.consume).run(stop)


if __name__ == '__main__':
    main()
