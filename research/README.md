# Experimento vigente: corpus ARP v2, baseline manual 0.7.0

Extensão offline opcional. O classificador operacional permanece intacto. Regras
Mamdani importadas da aplicação, ausência-como-zero e rampa ratio fixa 0,5–1,0.
Quatro genes: saturação de conflito, frequência, desvio e limiar superior.
A decisão foi tomada após diagnóstico do corpus, conforme
[ADR 0011](../docs/decisions/0011-corpus-arp-variavel-e-validade-experimental.md).

## Reproduzir

Na raiz, Python 3.11 ou superior:

```sh
python -m pip install -e ".[dev]"
python -m pip install -r requirements-optimization.txt
python -m netsentinel.optimization.diagnostics
python -m netsentinel.optimization.experiment --output research/results
python -m unittest discover -s research/tests -v
python tests/run_offline.py
python -m ruff check .
```

Para regenerar tudo sem sobrescrever a entrega, use `--output research/reproduction`
no comando de experimento. O runner gera dataset v2 se ausente, executa diagnóstico
antes de qualquer métrica, então roda 20 sementes por método. Se o manifesto já
existe, exige versão 2; manifestos anteriores são rejeitados, não completados com
features inventadas. Checkpoint é evidência parcial; nova execução reinicia as 40
rodadas. Os testes da entrega usam o diretório research/results incluído no ZIP.

Nenhuma interface é aberta e nenhum pacote é transmitido. Não depende de VMs,
nftables, Docker ou banco. Instalar DEAP permanece opcional para executar o MVP.

## Artefatos atuais e histórico inválido

- `results/report.md`: única comparação vigente; tabela e gráfico.
- `results/results.json` e `metrics.csv`: 40 execuções, parâmetros e métricas.
- `results/diagnostics.json`: distribuição de ratio, ativação e sensibilidade.
- `results/dataset/dataset.json` e `pcaps/`: manifestos e 600 PCAPs sintéticos.
- `historical-invalid/v060/`: comparação anterior inválida para a avaliação atual;
  usa outro baseline e corpus. A 0.6.0 não tinha ratio nas regras.
- `historical-invalid/v070-constant-ratio/`: comparação degenerada, invalidada;
  ratio=1 encobria os genes de frequência/desvio e bloqueava R4/R5.

Os históricos não foram apagados nem recalculados. Avisos INVALIDO.md e hashes
preserved-sha256.json identificam os originais. O antigo empate não é evidência
de equivalência entre algoritmos. Não misturar métricas de corpus/baselines diferentes.

## Dados sintéticos e rótulos

600 cenários independentes de 8 s, 420 benignos e 180 ataques; split por família
60/20/20 (360/120/120). Semente principal 20260919 conserva IDs, famílias,
rótulos, split, frequência total e carga de dados do corpus anterior.
RNG independente 20260920 escolhe a mistura ARP. Nenhum score define rótulo,
provider ou geração; diagnóstico de sensibilidade usa somente treino.

| Família | Rótulo | N | Tráfego | Fração replies sorteada |
|---|---:|---:|---|---|
| normal | 0 | 70 | 0,125–1,5 ARP/s, 2–8 UDP | 0–0,8 |
| burst | 0 | 70 | pico legítimo de 30–80 UDP | 0–0,8 |
| new_device | 0 | 70 | novo, sem baseline | 0–0,8 |
| discovery | 0 | 70 | 2–8 ARP/s legítimos | 0–0,6 |
| migration_ambiguous | 0 | 70 | IP migrado autorizado, dois anunciantes, 0,125–4 ARP/s | 0,1–1 |
| unknown_history | 0 | 70 | provider sem informação | 0–1 |
| poison_fast | 1 | 60 | alegação indevida com gateway, 3–16 ARP/s | 0,25–1 |
| poison_slow | 1 | 60 | alegação indevida com gateway, 0,25–6 ARP/s | 0,25–1 |
| poison_no_gateway_claim | 1 | 60 | gateway silencioso, 0,25–6 ARP/s | 0,25–1 |

Total ARP = max(1, round(frequência × 8)); replies = round(total × fração), com
mínimo de uma reply em migração/ataques. Requests = total − replies. Por isso o
ratio observado é quantizado e pode cair ligeiramente fora da faixa sorteada.
Cada família varia de fato, com sobreposição entre benignos e ataques; ratio
não identifica perfeitamente o rótulo. Ordens de opcodes são embaralhadas de modo
determinístico durante a janela, mantendo timestamps e sem janelas sobrepostas.

Requests op=1 usam broadcast Ethernet, hwdst zero, psrc 192.0.2.3 e pdst 192.0.2.2.
Replies op=2 alegam 192.0.2.1 ao destinatário. O alvo está autorizado a anunciar
essa identidade nos benignos; em ataques não. A autorização é ground truth do
cenário, não uma feature. Migração é o quase-ataque ambíguo: parte das evidências
se sobrepõe ao envenenamento e não é separável por simples inspeção dos inputs.

Payload UDP entre 64 e 1000 bytes. Fora das famílias fixas, 55% de probabilidade
KNOWN e 45% NEW; KNOWN recebe baseline histórico sintético de 100–700 **bytes/s**.
NEW/UNKNOWN não recebem baseline. Não se infere histórico da própria janela nem
se altera o Repository real. Conflito permanece 0 ou 0,5 (não cobre mais de dois
anunciantes). Bytes incluem cabeçalhos, medidos pela captura real; ratio/frequência
são extraídos depois da releitura do PCAP, não preenchidos artificialmente.

## Validade e limitação de cobertura

Diagnóstico anterior à busca: 219 ratios distintos, 575/600 exemplos com requests;
400/420 benignos com requests. No treino, frequência e desvio alteram scores e
decisões binárias quando variados isoladamente, sem mudar os demais genes.
R5 volta a disparar. R4 continua sem ativação neste corpus porque NEW não possui
baseline: sua cláusula de desvio baixo carece de evidência. Isso é limitação
explícita, distinta da saturação do ratio, e não se fabrica histórico para removê-la.
As cinco regras mantêm testes isolados; a comparação empírica cobre R1/R2/R3/R5.

O diagnóstico rejeita corpus degenerado e genes frequência/desvio sem efeito antes
do cálculo de métricas comparativas. Não impõe F1 mínimo, não seleciona cenários
por desempenho e não busca maximizar uma nota. Não comprova generalização real:
todas as famílias aparecem nos três splits, os intervalos são escolhas sintéticas,
e a prevalência de 30% de ataque não representa automaticamente uma rede doméstica.

## Método e referências

DEAP; população 40, 40 gerações, sementes 0–19 por algoritmo. SBX limitado 0,9,
eta=20; mutação polinomial 0,2 por indivíduo, 1/4 por gene, eta=20. AG maximiza F1,
torneio 3, elites 2. NSGA-II maximiza recall/minimiza FPR; seleção ambiental de
pais+filhos. Escolha na validação por F1, desempate FPR e genes lexicográficos.
Teste apenas para relato; média e desvio amostral ddof=1. Abstenções são não detecção,
com contagem explícita. O piso ratio fixo controla a comparação com o baseline;
a análise não prova que 0,5 seja ótimo. Nenhum modelo substitui a defesa operacional.

[CIC-IDS2017](https://www.unb.ca/cic/datasets/ids-2017.html) e
[UNSW-NB15](https://research.unsw.edu.au/projects/unsw-nb15-dataset) são referências
de caracterização/diversidade de tráfego benigno e malicioso, não fontes dos dados,
intervalos sorteados ou features desta entrega. Nenhum registro foi importado.
[Documentação DEAP](https://deap.readthedocs.io/en/master/api/tools.html).
A trilha própria ainda depende do aceite docente; VMs e cloud não foram validados.
