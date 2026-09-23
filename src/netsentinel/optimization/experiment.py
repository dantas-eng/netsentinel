"""AG/NSGA-II reproduzíveis, treino exclusivo e escolha por validação."""
import argparse
from collections import defaultdict
import copy
import csv
import hashlib
import importlib.metadata
import json
import random
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
from deap import base, creator, tools

from netsentinel.analysis.fuzzy.engine import infer as manual_infer
from netsentinel.optimization.classifier import Parameters, scores
from netsentinel.optimization.dataset import generate, inputs_of, load
from netsentinel.optimization.diagnostics import write as write_diagnostics

BOUNDS = [(0.1, 1.0), (1., 20.), (0.25, 4.), (50., 85.)]
LOW, HIGH = [b[0] for b in BOUNDS], [b[1] for b in BOUNDS]
POPULATION, GENERATIONS = 40, 40
METRICS = ['precision', 'recall', 'f1', 'fpr', 'abstentions']
creator.create('NetSentinelSingleFitness', base.Fitness, weights=(1.0,))
creator.create('NetSentinelMultiFitness', base.Fitness, weights=(1.0, -1.0))
creator.create('NetSentinelSingle', list, fitness=creator.NetSentinelSingleFitness)
creator.create('NetSentinelMulti', list, fitness=creator.NetSentinelMultiFitness)


def metrics(labels, values, threshold):
    labels = np.asarray(labels, dtype=bool)
    values = np.asarray(values, dtype=float)
    positive = values >= threshold  # NaN é não detecção, nunca removido do denominador.
    tp, fp = int(np.sum(positive & labels)), int(np.sum(positive & ~labels))
    fn, tn = int(np.sum(~positive & labels)), int(np.sum(~positive & ~labels))
    return {'precision': tp/(tp+fp) if tp+fp else 0.,
            'recall': tp/(tp+fn) if tp+fn else 0.,
            'f1': 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.,
            'fpr': fp/(fp+tn) if fp+tn else 0.,
            'abstentions': int(np.isnan(values).sum()),
            'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn}


def nondominated(items):
    return [item for item in items if not any(
        other['recall'] >= item['recall'] and other['fpr'] <= item['fpr'] and
        (other['recall'] > item['recall'] or other['fpr'] < item['fpr']) for other in items)]


def optimize(method, seed, training, validation):
    random.seed(seed)
    cls = creator.NetSentinelSingle if method == 'ga' else creator.NetSentinelMulti
    population = [cls(random.uniform(a, b) for a, b in BOUNDS) for _ in range(POPULATION)]
    cache = {}
    tx, ty = training
    vx, vy = validation

    def evaluate(ind):
        key = tuple(ind)
        if key not in cache:
            m = metrics(ty, scores(tx, Parameters.genes(ind)), ind[3])
            cache[key] = (m['f1'],) if method == 'ga' else (m['recall'], m['fpr'])
        ind.fitness.values = cache[key]

    for ind in population:
        evaluate(ind)
    archive = tools.HallOfFame(2) if method == 'ga' else tools.ParetoFront()
    archive.update(population)
    population = tools.selNSGA2(population, POPULATION) if method != 'ga' else population
    for _ in range(GENERATIONS):
        parents = (tools.selTournament(population, POPULATION-2, tournsize=3)
                   if method == 'ga' else tools.selTournamentDCD(population, POPULATION))
        children = list(map(copy.deepcopy, parents))
        for left, right in zip(children[::2], children[1::2]):
            if random.random() < 0.9:
                tools.cxSimulatedBinaryBounded(left, right, eta=20, low=LOW, up=HIGH)
        for child in children:
            if random.random() < 0.2:
                tools.mutPolynomialBounded(child, eta=20, low=LOW, up=HIGH, indpb=0.25)
            evaluate(child)
        archive.update(children)
        population = (list(map(copy.deepcopy, tools.selBest(population, 2))) + children
                      if method == 'ga' else tools.selNSGA2(population+children, POPULATION))
    # Seleção entre finalistas do treino; teste não é argumento desta função.
    candidates = list(archive)
    assessed = [(ind, metrics(vy, scores(vx, Parameters.genes(ind)), ind[3]))
                for ind in candidates]
    selected, validation_metrics = min(assessed, key=lambda pair: (
        -pair[1]['f1'], pair[1]['fpr'], tuple(pair[0])))
    front = [{'genes': list(ind), 'training': dict(zip(
        ['recall', 'fpr'] if method != 'ga' else ['f1'], ind.fitness.values))}
             for ind in candidates]
    return list(selected), validation_metrics, front, len(cache)


def run(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    data_dir = directory/'dataset'
    records = load(data_dir) if (data_dir/'dataset.json').exists() else generate(data_dir)
    diagnostics = write_diagnostics(directory)  # Antes de qualquer métrica comparativa.
    sets = {}
    for split in ('train', 'validation', 'test'):
        selected = [r for r in records if r['split'] == split]
        sets[split] = inputs_of(selected), [r['label'] for r in selected]
    x_test, y_test = sets['test']
    baseline = metrics(y_test, [manual_infer(x).score for x in x_test], 65)
    rows, details = [], []
    started = time.time()
    for method in ('ga', 'nsga2'):
        for seed in range(20):
            tick = time.time()
            genes, valid, front, evaluations = optimize(method, seed, sets['train'], sets['validation'])
            result = metrics(y_test, scores(x_test, Parameters.genes(genes)), genes[3])
            rows.append({'method': method, 'seed': seed, **result})
            details.append({'method': method, 'seed': seed, 'genes': genes,
                            'validation': valid, 'test': result, 'training_archive': front,
                            'unique_evaluations': evaluations, 'seconds': time.time()-tick})
            (directory/'checkpoint.json').write_text(json.dumps(details, indent=2)+'\n')
            print(f'{method} seed={seed:02d} test F1={result["f1"]:.4f} '
                  f'({time.time()-tick:.1f}s)', flush=True)
    summary = {method: {metric: {'mean': float(np.mean([r[metric] for r in rows
                                                     if r['method'] == method])),
                               'sample_sd': float(np.std([r[metric] for r in rows
                                                         if r['method'] == method], ddof=1))}
                        for metric in METRICS} for method in ('ga', 'nsga2')}
    output = {'baseline_test': baseline, 'summary_test': summary, 'runs': details,
              'protocol': {'baseline_version': '0.7.0', 'dataset_version': 2,
                           'ratio_decision': 'ADR 0011: piso fixo após diagnóstico do corpus',
                           'fixed_ratio': {'floor': 0.5, 'ceiling': 1.0},
                           'population': POPULATION, 'generations': GENERATIONS,
                           'seeds': list(range(20)), 'bounds': BOUNDS,
                           'baseline_parameters': asdict(Parameters())},
              'dataset_sha256': hashlib.sha256((data_dir/'dataset.json').read_bytes()).hexdigest(),
              'diagnostics': diagnostics,
              'versions': {name: importlib.metadata.version(name) for name in
                           ('deap', 'numpy', 'scikit-fuzzy', 'scapy', 'matplotlib')},
              'seconds': time.time()-started}
    (directory/'results.json').write_text(json.dumps(output, indent=2)+'\n')
    with (directory/'metrics.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report(directory, output)


def report(directory, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    # Frente empírica agrupada dos arquivos de treino, sem declarar ótimo global.
    points = [dict(item['training'], genes=item['genes']) for run in output['runs']
              if run['method'] == 'nsga2' for item in run['training_archive']]
    objective_points = {(p['recall'], p['fpr']): p for p in points}
    front = nondominated(list(objective_points.values()))
    unique = {(p['fpr'], p['recall']) for p in front}
    xs, ys = zip(*sorted(unique))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    axes[0].scatter([p['fpr'] for p in points], [p['recall'] for p in points],
                    alpha=.15, s=15, label='Arquivos das 20 sementes')
    axes[0].plot(xs, ys, 'o-', label='Não dominados agrupados')
    baseline = output['baseline_test']
    groups = {}
    for method, color, marker, size in (('ga', 'tab:blue', 'o', 65),
                                        ('nsga2', 'tab:orange', 's', 150)):
        runs = [r for r in output['runs'] if r['method'] == method]
        groups[method] = defaultdict(list)
        for run in runs:
            matrix = tuple(run['test'][key] for key in ('tp', 'fp', 'fn', 'tn'))
            groups[method][matrix].append(run)
        rows = [r['test'] for r in runs]
        # Cada semente é desenhada; sem jitter ou deslocamento das coordenadas.
        # Marcadores distintos preservam a visibilidade quando os métodos coincidem.
        axes[1].scatter([r['fpr'] for r in rows], [r['recall'] for r in rows],
                        label=f'{method.upper()} — {len(rows)} execuções',
                        alpha=.14, marker=marker, s=size,
                        facecolors=color if method == 'ga' else 'none',
                        edgecolors=color, linewidths=1.3)
        for cluster in groups[method].values():
            value = cluster[0]['test']
            axes[1].annotate(f'{method.upper()}: {len(cluster)}/{len(runs)}',
                             (value['fpr'], value['recall']), textcoords='offset points',
                             xytext=(10, -17 if method == 'ga' else 12),
                             fontsize=9, color=color)
    axes[1].scatter([baseline['fpr']], [baseline['recall']], marker='*', s=140, color='tab:green', label='Manual')
    for ax, title in zip(axes, ['Frente empírica — treino', 'Teste — 20 execuções por método']):
        ax.set(xlabel='Taxa de falso positivo', ylabel='Recall', title=title)
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    axes[1].margins(x=.15, y=.25)
    fig.savefig(directory/'pareto.png', dpi=180)
    plt.close(fig)
    text = ['# Comparação experimental — dados exclusivamente sintéticos', '',
            'Baseline: fuzzy manual 0.7.0. Ratio ARP usa rampa fixa 0,5–1,0; '
            'quatro genes são otimizados. O teste reservado não participa da busca '
            'nem da escolha de representantes.', '',
            'Corpus v2: requests e replies ARP reais em PCAPs sintéticos; ratio '
            'extraído pelo capturador. A verificação de variação e sensibilidade '
            'precedeu a decisão de manter o piso fixo (ADR 0011). As comparações '
            'anteriores estão invalidadas e preservadas em ../historical-invalid/.', '',
            '| Método | Precisão | Recall | F1 | FPR | Abstenções |',
            '|---|---:|---:|---:|---:|---:|']
    text.append('| Manual (determinístico) | '+ ' | '.join(f'{baseline[k]:.4f}' for k in METRICS)+' |')
    for method, summary in output['summary_test'].items():
        text.append('| '+method+' (20 sementes) | '+' | '.join(
            f'{summary[k]["mean"]:.4f} ± {summary[k]["sample_sd"]:.4f}' for k in METRICS)+' |')
    text += ['', 'Valores: média ± desvio-padrão amostral (ddof=1). O baseline é uma única '
             'execução determinística; a variação dos métodos mede somente aleatoriedade da busca '
             'neste split, não incerteza de generalização.', '',
             'Neste split sintético, ambos os métodos obtiveram F1 médio maior que o manual.'
             if all(v['f1']['mean'] > baseline['f1'] for v in output['summary_test'].values())
             else 'Neste split, pelo menos um método não superou o F1 do manual.', '',
             f'A frente agrupada contém {len(unique)} pontos objetivos distintos. '
             'As ligações no gráfico são guias visuais, não soluções intermediárias garantidas.', '',
             'O painel de teste plota as 20 execuções individuais de cada método, '
             'com transparência alpha=0,14, sem jitter. Círculos azuis representam AG e '
             'quadrados laranja vazados representam NSGA-II. Pontos coincidentes se '
             'sobrepõem; os rótulos informam quantas sementes ocupam cada ponto. '
             'O painel não mostra médias nem barras de erro; média e desvio-padrão '
             'permanecem na tabela.', '',
             '![Frente e teste](pareto.png)', '',
             'Não há garantia de superioridade sobre o manual. Sobreposição entre famílias '
             'benignas e ataques limita a separação pelas cinco entradas. Resultados não '
             'constituem validação em tráfego real ou nas VMs. Nenhuma configuração é promovida '
             'automaticamente à aplicação.', '',
             f'Tempo total de otimização/avaliação: {output["seconds"]:.1f} s.',
             'Dados, hashes de PCAP, sementes, parâmetros individuais, versões e arquivos de '
             'treino completos estão em dataset/dataset.json e results.json.']
    for method, summary in output['summary_test'].items():
        if (summary['fpr']['mean'] < baseline['fpr'] and
                summary['recall']['mean'] < baseline['recall']):
            text += ['', f'{method.upper()}: a redução média de falsos positivos vem '
                     'acompanhada de recall médio menor que o manual. F1 maior não '
                     'significa superioridade em todas as métricas.']
    diag = output['diagnostics']
    text += ['', '## Validade e cobertura do corpus', '',
             f'Ratio: {diag["ratio"]["all"]["distinct"]} valores distintos; '
             f'{diag["ratio"]["all"]["with_requests"]}/600 cenários com requests. '
             'Distribuição por classe e família em diagnostics.json.', '',
             'Sensibilidade no treino, entre os extremos de cada gene e demais '
             'parâmetros manuais (não são métricas de desempenho):', '',
             '| Gene | Scores alterados | Decisões binárias alteradas |',
             '|---|---:|---:|']
    for gene, values in diag['training_one_gene_at_a_time'].items():
        text.append(f'| {gene} | {values["score_changes"]} | '
                    f'{values["binary_decision_changes"]} |')
    text += ['', 'Ativação de regras no treino: ' + ', '.join(
        f'{key}={value}' for key, value in diag['training_rule_activation'].items()) + '.',
        '', diag['r4_limitation'], '',
        'A comparação exercita R1/R2/R3/R5; não comprova eficácia empírica de R4. '
        'O piso 0,5 foi mantido como controle da 0.7.0, não demonstrado ótimo.']
    nsga = [r for r in output['runs'] if r['method'] == 'nsga2']
    distinct = len({tuple(r['genes']) for r in nsga})
    frequencies = [r['genes'][1] for r in nsga]
    text += ['', '## Genótipos e decisões observadas', '',
             f'Verificação dos genes crus em `results.json`: {distinct} genótipos distintos '
             f'em {len(nsga)} execuções do NSGA-II. A saturação de frequência varia de '
             f'{min(frequencies):.8f} a {max(frequencies):.8f} anúncios/s '
             f'(aproximadamente {min(frequencies):.2f}–{max(frequencies):.2f}).', '',
             '| Método | Execuções | TP | FP | FN | TN | Sementes |',
             '|---|---:|---:|---:|---:|---:|---|']
    for method, clusters in groups.items():
        for matrix, cluster in sorted(clusters.items(), key=lambda item: -len(item[1])):
            seeds = ', '.join(str(run['seed']) for run in cluster)
            text.append(f'| {method.upper()} | {len(cluster)}/20 | ' +
                        ' | '.join(str(value) for value in matrix) + f' | {seeds} |')
    test_inputs = inputs_of([r for r in load(directory/'dataset') if r['split'] == 'test'])
    decisions = {tuple(scores(test_inputs, Parameters.genes(r['genes'])) >= r['genes'][3])
                 for r in nsga}
    text += ['', f'A comparação exemplo a exemplo encontrou {len(decisions)} vetor(es) '
             'distinto(s) de decisões binárias nas execuções do NSGA-II.']
    if distinct == len(nsga) and len(groups['nsga2']) == 1:
        text += ['', 'Os 20 genótipos comprovadamente distintos do NSGA-II convergem para '
                 'a mesma matriz de confusão no conjunto de teste. Isso é evidência de um '
                 'platô do comportamento de decisão avaliado nesse conjunto, não de '
                 'convergência genética. Não demonstra que os scores contínuos sejam '
                 'iguais ou que as decisões coincidam em dados fora do teste.']
    ga_sd = output['summary_test']['ga']['f1']['sample_sd']
    text += ['', f'O AG ocupa {len(groups["ga"])} grupo(s) de matriz de confusão; '
             f'o desvio-padrão amostral de F1 é {ga_sd:.8f}.']
    (directory/'report.md').write_text('\n'.join(text)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('research/results'))
    args = parser.parse_args()
    run(args.output)


if __name__ == '__main__':
    main()
