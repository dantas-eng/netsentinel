# ADR 0011 — Corrigir corpus ARP e verificar validade antes da otimização

## Status e problema

Aceita após regeneração e diagnóstico do corpus v2, antes de reexecutar AG/NSGA-II.
Complementa e corrige a ADR 0010. O empate nela relatado não é comparação válida:
ratio=1 em todos os exemplos saturava ratio_high=1, portanto o OR de R2/R3 era
sempre 1 e não dependia de frequência/desvio. Ratio_low=0 bloqueava R4/R5.
A restrição afetava dois genes, não apenas a qualidade preditiva do classificador.

Arquivar as duas tentativas anteriores em `research/historical-invalid/`:
`v060/` e `v070-constant-ratio/`. Ambas estão invalidadas para comparação atual.
A 0.6.0 não possuía ratio: não atribuímos retrospectivamente aquele mecanismo às
suas regras; seu corpus/regras não são comparáveis com a experiência corrigida.
Preservar arquivos e números originais, identificados por hashes e avisos.

## Corpus v2

Manter 600 cenários, famílias, rótulos, split 60/20/20, semente principal 20260919,
frequência total, reputação, baseline prévio, carga UDP e janela de 8 s. Usar um
RNG separado (20260920) para escolher fração de replies, sem consultar scores.
O número inteiro de replies é arredondado; requests = total − replies.
Ataques e migração exigem ao menos uma reply para manter a alegação de IP.
As faixas se sobrepõem entre classes e não vêm de estimativas em tráfego real.

| Família | Fração de replies sorteada antes do arredondamento |
|---|---|
| normal, burst, new_device | 0–0,8 |
| discovery | 0–0,6 |
| migration_ambiguous | 0,1–1 |
| unknown_history | 0–1 |
| poison_fast, poison_slow, poison_no_gateway_claim | 0,25–1 |

Requests são pacotes ARP op=1, destino Ethernet broadcast, hwdst zerado,
psrc próprio 192.0.2.3, pdst da vítima 192.0.2.2. Replies op=2 mantêm a alegação
192.0.2.1. Os opcodes são intercalados deterministicamente na janela. Não se
preenche a feature diretamente: PCAP é serializado, relido e processado pelo
CaptureService/FeatureExtractor da aplicação, sem transmissão de pacotes.

## Evidência antes da escolha do gene

`research/results/diagnostics.json` registra:

- 219 ratios distintos, mínimo 0, máximo 1; 575/600 cenários com requests.
- Benignos: 114 ratios distintos, 400/420 com requests; 300 abaixo/no piso,
  100 entre piso e teto, 20 no teto.
- Ataques: 142 ratios distintos; 175/180 com requests; também há sobreposição
  com benignos abaixo do piso.
- Treino, parâmetros manuais: R1 ativa em 114 exemplos, R2 em 163, R3 em 155,
  R4 em 0 e R5 em 77.
- Teste de sensibilidade no **treino**, movendo um gene entre os extremos e
  mantendo os demais manuais: conflito altera 114 scores/38 decisões binárias;
  frequência 199/43; desvio 77/28; limiar superior 0 scores/274 decisões.

R4 não é encoberta: NEW recebe baseline ausente pelo protocolo de providers,
logo não há evidência de desvio baixo para seu AND. Isso independe do ratio.
Não fabricar baseline de dispositivo novo para obter cobertura artificial.
R4 segue coberta por testes isolados de regras, mas esta comparação não mede
seu comportamento em dados reais. R5 foi reativada; frequência e desvio agora
alteram efetivamente scores e decisões no corpus de treino.

## Decisão: manter quatro genes e ratio fixo

Após essas verificações, manter o piso calibrado da 0.7.0 em 0,5 e o teto em 1.
Não introduzir quinto gene. A degeneração foi removida sem ampliar a busca;
conservar ratio igual no baseline e candidatos permite estudar os quatro
parâmetros já aprovados sem misturar correção do corpus e nova hipótese de
otimização. A distribuição cobre abaixo, dentro e acima da rampa e os genes
voltaram a ter influência observável.

Isso **não prova que 0,5 é ótimo**, nem que otimizar o piso seja inútil. Um quinto
gene pode ser avaliado em experimento separado, com faixas e comparação de
ablação próprias. Nesta execução não há seleção do piso por métricas de teste.

## Reexecução e prevenção

Mesmo DEAP, quatro genes e faixas, operadores, população 40, gerações 40 e sementes
0–19 por método. Treino para fitness; validação para representante; teste só para
relato. Dataset v2 e relatório substituem a comparação corrente, não o histórico.
O baseline operacional FuzzyRiskStrategy 0.7.0 permanece intocado.

O runner exige manifesto v2, diagnóstico de variação de ratio e requests,
sensibilidade de frequência/desvio e ativação de R5 antes de qualquer avaliação
comparativa. Não há piso mínimo de F1 nem promessa de melhoria. As verificações
não substituem representatividade em rede real, ensaio das VMs ou aceite docente.
