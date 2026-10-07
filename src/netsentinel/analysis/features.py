"""Extrai evidência por origem Ethernet sem atribuir autoria de um ataque."""
from collections import defaultdict
from math import isfinite
from netsentinel.analysis.contracts import BaselineProvider, Reputation, ReputationProvider
from netsentinel.analysis.models import RiskInputs

ARP_RATIO_MIN_PACKETS = 4


class FeatureExtractor:
    def __init__(self, reputation: ReputationProvider, baseline: BaselineProvider):
        self.reputation = reputation
        self.baseline = baseline

    def extract(self, snapshot: dict) -> dict[str, RiskInputs]:
        """Conflito poupa dono reconhecido e razão exige amostra mínima (ADR 0013)."""
        claims_by_ip = defaultdict(set)
        sources_by_ip = defaultdict(set)
        ips_by_source = defaultdict(set)
        for claim in snapshot["arp_claims"]:
            if claim["ip"] == "0.0.0.0":
                continue
            claims_by_ip[claim["ip"]].add(claim["claimed_mac"].lower())
            source = claim["source_mac"].lower()
            sources_by_ip[claim["ip"]].add(source)
            ips_by_source[source].add(claim["ip"])

        # Uma consulta por MAC; chave minúscula para casar com as alegações.
        cache = {}

        def reputation_of(mac):
            if mac.lower() not in cache:
                cache[mac.lower()] = self.reputation.get_reputation(mac)
            return cache[mac.lower()]

        def conflict_at(ip, mac):
            sources = sources_by_ip[ip]
            known = {m for m in sources if reputation_of(m) == Reputation.KNOWN}
            if mac in known and len(known) < len(sources):
                return 0.0
            return 1 - 1 / len(claims_by_ip[ip])

        # Qualidade invalida as medições derivadas da captura, não o resultado.
        # Mesmo nesses casos a inferência é executada com graus zero nos inputs ausentes.
        quality = []
        if snapshot["incomplete"]:
            quality.append("capture_incomplete")
        if snapshot["warming_up"]:
            quality.append("capture_warming_up")
        duration = snapshot["observed_seconds"]
        duration_valid = duration is not None and isfinite(duration) and duration > 0
        results = {}
        for mac, device in snapshot["devices"].items():
            reasons = list(quality)
            reputation = reputation_of(mac)
            if reputation is None or reputation == Reputation.UNKNOWN:
                reputation_value = None
                reasons.append("reputation_unavailable")
            elif reputation in (Reputation.KNOWN, Reputation.NEW):
                reputation_value = reputation.value
            else:
                raise ValueError("Provider retornou reputação inválida.")

            baseline = self.baseline.get_baseline_bps(mac)
            baseline_valid = baseline is not None and isfinite(baseline) and baseline > 0
            if not baseline_valid:
                reasons.append("baseline_missing_or_nonpositive_or_nonfinite")

            conflict = frequency = deviation = ratio = None
            if not quality:
                conflict = max((conflict_at(ip, mac.lower())
                                for ip in ips_by_source[mac.lower()]), default=0.0)
                total_arp = device["arp_requests"] + device["arp_replies"]
                if total_arp >= ARP_RATIO_MIN_PACKETS:
                    ratio = device["arp_replies"] / total_arp
                elif total_arp > 0:
                    reasons.append("arp_reply_ratio_insufficient_sample")
                else:
                    reasons.append("arp_reply_ratio_unavailable")
                if duration_valid:
                    frequency = total_arp / duration
                    if baseline_valid:
                        rate = device["bytes"] / duration
                        deviation = abs(rate - baseline) / baseline
                else:
                    reasons.append("observed_duration_unavailable")
            results[mac] = RiskInputs(conflict, frequency, reputation_value,
                                      deviation, ratio, tuple(reasons))
        return results
