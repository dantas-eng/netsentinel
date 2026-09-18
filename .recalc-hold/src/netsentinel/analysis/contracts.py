"""Strategy e providers: a análise não importa banco, Flask ou Scapy."""
from enum import Enum
from typing import Protocol
from netsentinel.analysis.models import RiskResult


class Reputation(str, Enum):
    KNOWN = "known"
    NEW = "new"
    UNKNOWN = "unknown"


class ReputationProvider(Protocol):
    def get_reputation(self, mac: str) -> Reputation | None:
        """UNKNOWN/None significa ausência de evidência, não dispositivo novo."""
        ...


class BaselineProvider(Protocol):
    def get_baseline_bps(self, mac: str) -> float | None:
        """Bytes capturados por segundo por MAC de origem; mesma unidade da captura."""
        ...


class ClassificationStrategy(Protocol):
    def classify(self, snapshot: dict) -> dict[str, RiskResult]:
        ...
