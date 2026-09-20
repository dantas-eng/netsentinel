"""Sem interface automática ou limiares fuzzy implícitos."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class CaptureConfig:
    interface: str
    window_seconds: float
    max_observations: int
    isolated_lab: bool

    def __post_init__(self):
        if not self.interface.strip() or self.interface == "any":
            raise ValueError("Informe uma interface específica do laboratório.")
        if not isfinite(self.window_seconds) or self.window_seconds <= 0:
            raise ValueError("A janela deve ser positiva e finita.")
        if self.max_observations < 1:
            raise ValueError("O limite de observações deve ser positivo.")
        if not self.isolated_lab:
            raise ValueError("Captura real permitida apenas no laboratório isolado.")
