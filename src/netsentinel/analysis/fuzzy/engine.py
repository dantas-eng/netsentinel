"""Mamdani explícito com primitivas scikit-fuzzy e rastreabilidade por regra.

A API de baixo nível permite pertinências todas zero para input ausente,
sem inventar um escalar substituto para ControlSystemSimulation.
"""
import numpy as np
import skfuzzy as fuzz
from netsentinel.analysis.contracts import BaselineProvider, ReputationProvider
from netsentinel.analysis.features import FeatureExtractor
from netsentinel.analysis.models import RiskInputs, RiskResult
from netsentinel.analysis.fuzzy.membership import fuzzify
from netsentinel.analysis.fuzzy.rules import evaluate


def label_score(score: float) -> str:
    if score < 35:
        return "confiável"
    if score < 65:
        return "desconhecido"
    return "suspeito"


def output_sets(universe):
    return {
        "low": fuzz.trapmf(universe, [0, 0, 20, 40]),
        "medium": fuzz.trimf(universe, [30, 50, 70]),
        "high": fuzz.trapmf(universe, [60, 80, 100, 100]),
    }


def infer(inputs: RiskInputs) -> RiskResult:
    memberships = fuzzify(inputs)
    strengths = evaluate(memberships)
    # Única condição de abstenção: nenhuma regra ativa, após avaliar todas.
    if max(strengths.values()) == 0.0:
        return RiskResult(None, None, "no_rule_activated", inputs, memberships, strengths)

    levels = {"low": strengths["R5"],
              "medium": max(strengths["R3"], strengths["R4"]),
              "high": max(strengths["R1"], strengths["R2"])}
    universe = np.linspace(0.0, 100.0, 1001)
    curves = output_sets(universe)
    # Inserir pontos dos cortes evita perder vértices no centroide.
    cuts = [point for name, level in levels.items()
            for point in fuzz.interp_universe(universe, curves[name], level)]
    universe = np.union1d(universe, cuts)
    curves = output_sets(universe)
    clipped = [np.fmin(levels[name], curve) for name, curve in curves.items()]
    # Inserir também cruzamentos entre saídas recortadas para integrar o envelope.
    crossings = []
    for i, left in enumerate(clipped):
        for right in clipped[i + 1:]:
            diff = left - right
            for j in np.where(diff[:-1] * diff[1:] < 0)[0]:
                crossings.append(universe[j] + (universe[j + 1] - universe[j]) *
                                 diff[j] / (diff[j] - diff[j + 1]))
    universe = np.union1d(universe, crossings)
    curves = output_sets(universe)
    aggregate = np.fmax.reduce([np.fmin(levels[name], curve)
                               for name, curve in curves.items()])
    score = float(fuzz.defuzz(universe, aggregate, "centroid"))
    return RiskResult(score, label_score(score), None, inputs, memberships, strengths)


class FuzzyRiskStrategy:
    """Implementa ClassificationStrategy por contrato estrutural (Protocol)."""
    def __init__(self, reputation_provider: ReputationProvider,
                 baseline_provider: BaselineProvider):
        self.extractor = FeatureExtractor(reputation_provider, baseline_provider)

    def classify(self, snapshot: dict) -> dict[str, RiskResult]:
        return {mac: infer(inputs) for mac, inputs in self.extractor.extract(snapshot).items()}
