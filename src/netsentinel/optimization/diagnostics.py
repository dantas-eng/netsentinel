"""Pré-condições experimentais sem usar métricas do teste para escolher parâmetros."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from netsentinel.optimization.classifier import Parameters, rule_data, scores
from netsentinel.optimization.dataset import inputs_of, load


def diagnose(records):
    def distribution(rows):
        ratios = [row['inputs']['arp_reply_ratio'] for row in rows]
        return {'n': len(rows), 'min': min(ratios), 'max': max(ratios),
                'distinct': len(set(ratios)),
                'at_or_below_floor': sum(x <= .5 for x in ratios),
                'between_floor_and_ceiling': sum(.5 < x < 1 for x in ratios),
                'at_ceiling': sum(x == 1 for x in ratios),
                'with_requests': sum(r['config']['arp_reply_count'] < r['config']['arp_count']
                                     for r in rows)}

    inputs = inputs_of([r for r in records if r['split'] == 'train'])
    activation = {name: sum(rule_data(x, Parameters())[1][name] > 0 for x in inputs)
                  for name in ('R1', 'R2', 'R3', 'R4', 'R5')}
    sensitivity = {}
    for index, (name, low, high) in enumerate((('conflict', .1, 1.), ('frequency', 1., 20.),
                                              ('deviation', .25, 4.), ('upper', 50., 85.))):
        left, right = [1., 5., 1., 65.], [1., 5., 1., 65.]
        left[index], right[index] = low, high
        a, b = scores(inputs, Parameters.genes(left)), scores(inputs, Parameters.genes(right))
        changed_scores = ~(np.isclose(a, b, atol=1e-9, rtol=0, equal_nan=True))
        changed_decisions = (a >= left[3]) != (b >= right[3])
        sensitivity[name] = {'score_changes': int(changed_scores.sum()),
                             'binary_decision_changes': int(changed_decisions.sum()),
                             'low': low, 'high': high}
    return {'scope': 'Distribuição do corpus; ativação e sensibilidade apenas no treino.',
            'ratio': {'all': distribution(records),
                      'benign': distribution([r for r in records if r['label'] == 0]),
                      'attack': distribution([r for r in records if r['label'] == 1])},
            'by_family': {family: distribution([r for r in records if r['family'] == family])
                          for family in sorted({r['family'] for r in records})},
            'training_rule_activation': activation,
            'training_one_gene_at_a_time': sensitivity,
            'r4_limitation': 'NEW sem baseline não confirma desvio baixo: R4 permanece '
                             'inativa por ausência de histórico, não por ratio saturado.'}


def validate(diagnostics):
    for group in ('all', 'benign', 'attack'):
        item = diagnostics['ratio'][group]
        if item['distinct'] < 2 or not item['with_requests']:
            raise ValueError(f'Corpus degenerado: ratio não varia ou não há requests ({group}).')
    for name in ('frequency', 'deviation'):
        if (diagnostics['training_one_gene_at_a_time'][name]['score_changes'] == 0 or
                diagnostics['training_one_gene_at_a_time'][name]['binary_decision_changes'] == 0):
            raise ValueError(f'Gene sem efeito na inferência de treino: {name}.')
    if not diagnostics['training_rule_activation']['R5']:
        raise ValueError('R5 nunca dispara no treino: investigar cobertura antes da busca.')


def write(directory):
    directory = Path(directory)
    data = diagnose(load(directory/'dataset'))
    data['dataset_sha256'] = hashlib.sha256((directory/'dataset/dataset.json').read_bytes()).hexdigest()
    validate(data)
    (directory/'diagnostics.json').write_text(json.dumps(data, indent=2)+'\n')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('research/results'))
    print(json.dumps(write(parser.parse_args().output), indent=2))
