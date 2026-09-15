#!/usr/bin/env python3
"""Consistência interna do motor fuzzy em cenários sintéticos.

Não mede acurácia em rede real. A varredura de RATIO_HIGH_FLOOR substitui
um limiar provisório por uma escolha justificada no próprio relatório.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from netsentinel.analysis.contracts import Reputation
from netsentinel.analysis.fuzzy import FuzzyRiskStrategy
from netsentinel.analysis.fuzzy import membership

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "docs/validation/fuzzy-metrics.md"
FLOORS = (0.3, 0.4, 0.5, 0.6, 0.7)
OUTCOMES = ("confiável", "desconhecido", "suspeito", None)
LABEL_NAMES = {None: "abstenção"}


@dataclass(frozen=True)
class Scenario:
    name: str
    snapshot: dict
    reputation: dict
    baseline: dict
    expected: str | None
    mac: str = "aa"


class _FixedMap:
    def __init__(self, values):
        self._values = values

    def get_reputation(self, mac):
        return self._values.get(mac)

    def get_baseline_bps(self, mac):
        return self._values.get(mac)


def _device(requests=0, replies=0, nbytes=1000, mac="aa"):
    return {mac: dict(bytes=nbytes, arp_requests=requests, arp_replies=replies)}


def _snapshot(devices, claims=(), seconds=10, incomplete=False, warming_up=False):
    return dict(
        incomplete=incomplete,
        warming_up=warming_up,
        observed_seconds=seconds,
        devices=devices,
        arp_claims=list(claims),
    )


def _quiet(requests, replies, nbytes=10000, seconds=100):
    return _snapshot(
        _device(requests=requests, replies=replies, nbytes=nbytes), seconds=seconds
    )


def _flood(requests=0, replies=50):
    return _snapshot(_device(requests=requests, replies=replies))


_CONFLICT = (
    dict(ip="192.0.2.1", claimed_mac="aa", source_mac="aa", count=1),
    dict(ip="192.0.2.1", claimed_mac="bb", source_mac="bb", count=1),
)

SCENARIOS = (
    Scenario("quiet_known_balanced", _quiet(1, 1), {"aa": Reputation.KNOWN}, {"aa": 100}, "confiável"),
    Scenario("quiet_new_balanced", _quiet(1, 1), {"aa": Reputation.NEW}, {"aa": 100}, "desconhecido"),
    Scenario("reply_flood_new", _flood(), {"aa": Reputation.NEW}, {}, "suspeito"),
    Scenario("reply_flood_known", _flood(), {"aa": Reputation.KNOWN}, {}, "desconhecido"),
    Scenario(
        "ip_conflict",
        _snapshot(_device(), _CONFLICT),
        {"aa": Reputation.UNKNOWN},
        {},
        "suspeito",
    ),
    Scenario("no_arp_known", _snapshot(_device()), {"aa": Reputation.KNOWN}, {"aa": 100}, None),
    Scenario("incomplete_window", _snapshot(_device(replies=50), incomplete=True), {"aa": Reputation.NEW}, {}, None),
    Scenario("unknown_rep_high_freq", _flood(), {"aa": Reputation.UNKNOWN}, {}, None),
    Scenario("warming_up", _snapshot(_device(replies=50), warming_up=True), {"aa": Reputation.KNOWN}, {"aa": 100}, None),
    Scenario("quiet_known_request_heavy", _quiet(7, 3), {"aa": Reputation.KNOWN}, {"aa": 100}, "confiável"),
    Scenario(
        "quiet_known_reply_heavy",
        _quiet(2, 8, nbytes=50000, seconds=500),
        {"aa": Reputation.KNOWN},
        {"aa": 100},
        "desconhecido",
    ),
    Scenario(
        "quiet_new_reply_lean",
        _quiet(7, 13, nbytes=100000, seconds=1000),
        {"aa": Reputation.NEW},
        {"aa": 100},
        "desconhecido",
    ),
    Scenario("new_high_freq_balanced", _flood(25, 25), {"aa": Reputation.NEW}, {}, "suspeito"),
    Scenario("known_high_freq_balanced", _flood(25, 25), {"aa": Reputation.KNOWN}, {}, "desconhecido"),
    Scenario("known_high_deviation", _quiet(1, 1, nbytes=100000), {"aa": Reputation.KNOWN}, {"aa": 100}, "desconhecido"),
)


def _predict(scenario: Scenario) -> str | None:
    engine = FuzzyRiskStrategy(_FixedMap(scenario.reputation), _FixedMap(scenario.baseline))
    return engine.classify(scenario.snapshot)[scenario.mac].classification


def _metrics(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def confusion(scenarios=SCENARIOS) -> dict:
    matrix = {expected: {predicted: 0 for predicted in OUTCOMES} for expected in OUTCOMES}
    misses = []
    abstentions = 0
    correct = 0
    for scenario in scenarios:
        predicted = _predict(scenario)
        matrix[scenario.expected][predicted] += 1
        if predicted is None:
            abstentions += 1
        if predicted == scenario.expected:
            correct += 1
        else:
            misses.append(
                {"name": scenario.name, "expected": scenario.expected, "predicted": predicted}
            )
    per_class = {}
    for label in OUTCOMES:
        tp = matrix[label][label]
        fp = sum(matrix[other][label] for other in OUTCOMES if other != label)
        fn = sum(matrix[label][other] for other in OUTCOMES if other != label)
        precision, recall, f1 = _metrics(tp, fp, fn)
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(matrix[label].values()),
        }
    n = len(scenarios)
    return {
        "matrix": matrix,
        "per_class": per_class,
        "misses": misses,
        "abstention_rate": abstentions / n if n else 0.0,
        "correct": correct,
        "n": n,
    }


def sweep(floors=FLOORS) -> list[dict]:
    rows = []
    for floor in floors:
        with patch.object(membership, "RATIO_HIGH_FLOOR", floor):
            row = confusion(SCENARIOS)
            row["floor"] = floor
            rows.append(row)
    return rows


def choose_floor(rows) -> float:
    return max(rows, key=lambda row: (row["correct"], -row["abstention_rate"], row["floor"]))["floor"]


def _shown(label) -> str:
    return LABEL_NAMES.get(label, label)


def _pct(value: float) -> str:
    return f"{value:.3f}"


def report() -> str:
    current = confusion(SCENARIOS)
    rows = sweep(FLOORS)
    recommended = choose_floor(rows)
    lines = [
        "# Métricas internas do motor fuzzy",
        "",
        "## O que este relatório não afirma",
        "",
        "Os cenários são sintéticos e escritos pela equipe. O harness mede",
        "consistência interna e sensibilidade ao limiar da razão de replies,",
        "não acurácia nem taxa de falso positivo em rede real. Apresentar estes",
        "números como acurácia do sistema seria enganoso.",
        "",
        f"Piso vigente em `RATIO_HIGH_FLOOR`: `{membership.RATIO_HIGH_FLOOR}`.",
        "Piso recomendado pelo critério (maior `correct`, menor",
        f"`abstention_rate`, valor mais alto): `{recommended}`.",
        "",
        "## Matriz de confusão",
        "",
        "| esperado \\ previsto | " + " | ".join(_shown(label) for label in OUTCOMES) + " |",
        "| --- | " + " | ".join("---" for _ in OUTCOMES) + " |",
    ]
    for expected in OUTCOMES:
        cells = " | ".join(str(current["matrix"][expected][predicted]) for predicted in OUTCOMES)
        lines.append(f"| {_shown(expected)} | {cells} |")
    lines.extend(["", "## Por classe", "", "| classe | precision | recall | F1 | support |", "| --- | --- | --- | --- | --- |"])
    for label in OUTCOMES:
        stats = current["per_class"][label]
        lines.append(
            f"| {_shown(label)} | {_pct(stats['precision'])} | {_pct(stats['recall'])} | "
            f"{_pct(stats['f1'])} | {stats['support']} |"
        )
    lines.extend([
        "",
        f"Acertos: {current['correct']} / {current['n']}.",
        f"Taxa de abstenção (previsto nulo): {_pct(current['abstention_rate'])}.",
        "",
        "## Erros",
        "",
    ])
    if current["misses"]:
        lines.append("| cenário | esperado | previsto |")
        lines.append("| --- | --- | --- |")
        for miss in current["misses"]:
            lines.append(
                f"| {miss['name']} | {_shown(miss['expected'])} | {_shown(miss['predicted'])} |"
            )
    else:
        lines.append("Nenhum desacordo entre rótulo esperado e classificação do motor.")
    lines.extend([
        "",
        "## Varredura de `RATIO_HIGH_FLOOR`",
        "",
        "| floor | correct | abstention_rate |",
        "| --- | --- | --- |",
    ])
    for row in rows:
        lines.append(f"| {row['floor']} | {row['correct']} | {_pct(row['abstention_rate'])} |")
    lines.append("")
    return "\n".join(lines)


def _jsonable(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return {("null" if key is None else key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def payload() -> dict:
    current = confusion(SCENARIOS)
    rows = sweep(FLOORS)
    return {
        "floor": membership.RATIO_HIGH_FLOOR,
        "recommended_floor": choose_floor(rows),
        "confusion": _jsonable(current),
        "sweep": _jsonable(rows),
    }


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Harness de consistência interna do motor fuzzy.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("-o", "--output", default=str(DEFAULT_REPORT))
    args = parser.parse_args(argv)
    if args.json:
        print(json.dumps(payload(), ensure_ascii=False, indent=2))
        return
    Path(args.output).write_text(report(), encoding="utf-8")


if __name__ == "__main__":
    main()
