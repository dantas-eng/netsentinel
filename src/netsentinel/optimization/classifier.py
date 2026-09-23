"""Mamdani parametrizado, reutilizando as regras originais sem modificá-las."""
from dataclasses import dataclass
from math import isfinite

import numpy as np

from netsentinel.analysis.features import FeatureExtractor
from netsentinel.analysis.fuzzy.rules import evaluate
from netsentinel.analysis.fuzzy.membership import RATIO_HIGH_FLOOR, ramp_from
from netsentinel.analysis.models import RiskResult


@dataclass(frozen=True)
class Parameters:
    conflict: float = 1.0
    frequency: float = 5.0
    deviation: float = 1.0
    lower: float = 35.0
    upper: float = 65.0

    def __post_init__(self):
        if any(not isfinite(x) or x <= 0 for x in
               (self.conflict, self.frequency, self.deviation)):
            raise ValueError('Saturações devem ser positivas e finitas.')
        if not 0 <= self.lower < self.upper <= 100:
            raise ValueError('Exige 0 <= lower < upper <= 100.')

    @classmethod
    def genes(cls, genes):
        c, f, d, upper = genes
        return cls(c, f, d, 35.0, upper)


def memberships(inputs, parameters):
    def pair(value, saturation):
        if value is None:
            return {'low': 0.0, 'high': 0.0}
        if not isfinite(value) or value < 0:
            raise ValueError('Feature deve ser finita e não negativa.')
        high = min(value / saturation, 1.0)
        return {'low': 1.0 - high, 'high': high}

    if inputs.reputation not in (None, 'new', 'known'):
        raise ValueError('Reputação inválida.')
    return {
        'conflict': pair(inputs.conflict, parameters.conflict),
        'frequency': pair(inputs.arp_frequency, parameters.frequency),
        'deviation': pair(inputs.volume_deviation, parameters.deviation),
        'ratio': ramp_from(inputs.arp_reply_ratio, RATIO_HIGH_FLOOR, 1.0),
        'reputation': {'new': float(inputs.reputation == 'new'),
                       'known': float(inputs.reputation == 'known')},
    }


def centroids(levels):
    """Integração exata do envelope linear por partes, vetorizada por exemplo.

    Inclui vértices dos consequentes, cortes e interseções entre segmentos.
    Não usa discretização aproximada para acelerar a busca experimental.
    NaN representa exclusivamente ausência de qualquer regra ativada.
    """
    levels = np.asarray(levels, dtype=float).reshape(-1, 3)
    n = len(levels)
    lo, mid, hi = levels.T
    knots = np.broadcast_to([0., 20., 30., 40., 50., 60., 70., 80., 100.], (n, 9))
    x = np.sort(np.column_stack((knots, 40-20*lo, 30+20*mid,
                                70-20*mid, 60+20*hi)), axis=1)

    def curves(points):
        raw = np.stack((np.clip((40-points)/20, 0, 1),
                        np.clip(np.minimum((points-30)/20, (70-points)/20), 0, 1),
                        np.clip((points-60)/20, 0, 1)), axis=2)
        return np.minimum(raw, levels[:, None, :])

    y = curves(x)
    crossings = []
    for a, b in ((0, 1), (0, 2), (1, 2)):
        diff = y[:, :, a] - y[:, :, b]
        left, right = diff[:, :-1], diff[:, 1:]
        fraction = np.divide(left, left-right, out=np.zeros_like(left),
                             where=(left * right < 0))
        crossings.append(x[:, :-1] + np.diff(x, axis=1) * fraction)
    x = np.sort(np.column_stack((x, *crossings)), axis=1)
    y = curves(x).max(axis=2)
    width = np.diff(x, axis=1)
    y0, y1 = y[:, :-1], y[:, 1:]
    area = width * (y0+y1)/2
    moment = x[:, :-1]*area + width**2 * (y0+2*y1)/6
    return np.divide(moment.sum(axis=1), area.sum(axis=1),
                     out=np.full(n, np.nan), where=area.sum(axis=1) > 0)


def rule_data(inputs, parameters):
    member = memberships(inputs, parameters)
    rules = evaluate(member)
    return member, rules, [rules['R5'], max(rules['R3'], rules['R4']),
                           max(rules['R1'], rules['R2'])]


def scores(inputs, parameters):
    return centroids([rule_data(item, parameters)[2] for item in inputs])


class ParameterizedFuzzyRiskStrategy:
    """Segunda ClassificationStrategy; providers permanecem injetados."""
    def __init__(self, reputation_provider, baseline_provider, parameters=Parameters()):
        self.extractor = FeatureExtractor(reputation_provider, baseline_provider)
        self.parameters = parameters

    def infer(self, inputs):
        member, rules, levels = rule_data(inputs, self.parameters)
        score = float(centroids([levels])[0])
        if np.isnan(score):
            return RiskResult(None, None, 'no_rule_activated', inputs, member, rules)
        label = ('confiável' if score < self.parameters.lower else
                 'desconhecido' if score < self.parameters.upper else 'suspeito')
        return RiskResult(score, label, None, inputs, member, rules)

    def classify(self, snapshot):
        return {mac: self.infer(inputs)
                for mac, inputs in self.extractor.extract(snapshot).items()}
