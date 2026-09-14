"""Ausência não é zero numérico: gera zero em TODOS os conjuntos."""
from math import isfinite
import numpy as np
import skfuzzy as fuzz
from netsentinel.analysis.models import RiskInputs


def complementary(value: float | None, saturation: float) -> dict[str, float]:
    if value is None:
        return {"low": 0.0, "high": 0.0}
    if not isfinite(value) or value < 0:
        raise ValueError("Input presente deve ser finito e não negativo.")
    universe = np.array([0.0, saturation])
    clipped = min(value, saturation)
    return {
        "low": float(fuzz.interp_membership(universe, [1.0, 0.0], clipped)),
        "high": float(fuzz.interp_membership(universe, [0.0, 1.0], clipped)),
    }


def fuzzify(inputs: RiskInputs) -> dict[str, dict[str, float]]:
    if inputs.reputation not in (None, "known", "new"):
        raise ValueError("Reputação deve ser known, new ou None.")
    return {
        "conflict": complementary(inputs.conflict, 1.0),
        "frequency": complementary(inputs.arp_frequency, 5.0),
        "deviation": complementary(inputs.volume_deviation, 1.0),
        "reputation": {"known": float(inputs.reputation == "known"),
                       "new": float(inputs.reputation == "new")},
    }
