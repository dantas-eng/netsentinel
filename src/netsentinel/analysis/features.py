"""Extrai evidência por origem Ethernet sem atribuir autoria de um ataque."""
from collections import defaultdict
from math import isfinite
from netsentinel.analysis.contracts import BaselineProvider, Reputation, ReputationProvider
from netsentinel.analysis.models import RiskInputs


class FeatureExtractor:
    def __init__(self, reputation: ReputationProvider, baseline: BaselineProvider):
        self.reputation = reputation
        self.baseline = baseline

    def extract(self, snapshot: dict) -> dict[str, RiskInputs]:
        claims_by_ip = defaultdict(set)
        ips_by_source = defaultdict(set)
        for claim in snapshot["arp_claims"]:
            if claim["ip"] == "0.0.0.0":
                continue
            claims_by_ip[claim["ip"]].add(claim["claimed_mac"].lower())
            ips_by_source[claim["source_mac"].lower()].add(claim["ip"])

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
            reputation = self.reputation.get_reputation(mac)
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
                conflict = max((1 - 1 / len(claims_by_ip[ip])
                                for ip in ips_by_source[mac.lower()]), default=0.0)
                total_arp = device["arp_requests"] + device["arp_replies"]
                if total_arp > 0:
                    ratio = device["arp_replies"] / total_arp
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
