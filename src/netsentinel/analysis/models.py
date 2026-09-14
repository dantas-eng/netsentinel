"""Valores ausentes permanecem None até a fuzzificação."""
from dataclasses import dataclass


@dataclass(frozen=True)
class RiskInputs:
    conflict: float | None
    arp_frequency: float | None
    reputation: str | None
    volume_deviation: float | None
    missing_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class RiskResult:
    score: float | None
    classification: str | None
    reason: str | None
    inputs: RiskInputs
    memberships: dict[str, dict[str, float]]
    rule_strengths: dict[str, float]
