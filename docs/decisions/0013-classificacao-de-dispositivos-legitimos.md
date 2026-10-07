# ADR 0013 — Classificação de dispositivos legítimos

## Status e problema

Decisões D1–D3 aprovadas pelo grupo em 07/10/2026. Complementa as ADRs 0008 e 0011 e altera o
modelo fuzzy descrito nelas; o desenho completo está em
[specs/2026-10-07-classificacao-legitimos-design.md](../specs/2026-10-07-classificacao-legitimos-design.md).

Um ensaio exploratório em 06/10/2026, com kernel, Scapy e nftables em quatro
namespaces de rede (gateway, Vítima, Atacante e Sensor numa bridge em modo hub),
não versionado, indicou detecção e mitigação do Atacante, mas mostrou que a
classificação dos dispositivos legítimos enganava quem olhava o painel. Esse
ensaio não é evidência de aceite; a validação versionada com o modelo novo está
em [`docs/validation/ensaio-namespaces-2026-10-07.md`](../validation/ensaio-namespaces-2026-10-07.md).
O ensaio nas quatro VMs segue pendente.

1. **Gateway suspeito (81) durante o ataque.** O conflito `1 - 1/n` por IP
   punia todos os MACs que alegam o IP disputado, inclusive o dono legítimo.
2. **Legítimos nunca chegavam a confiável.** R5 exige razão ARP baixa e desvio
   baixo. Sem ARP na janela ou sem baseline, as duas pertinências ficam em zero
   e R5 não dispara: o dispositivo ficava sem avaliação ou em 50.
3. **Uma resposta ARP normal virava anomalia.** Com uma única resposta na
   janela, a razão de replies é 1, `ratio_high` = 1 e R3 levava o gateway a 50.

Critério de sucesso: dispositivo reconhecido e sem sinal ruim aparece
confiável; o dono legítimo de um IP disputado não é penalizado; a detecção do
Atacante não muda. As fixtures de aceitação mantêm 82,38 e 84,44.

## Decisão

### D1. Conhecido e silencioso é confiável

Ausência de ARP na janela passa a significar "nada suspeito medido", não "falta
de prova". Nas regras R4 e R5, desvio e razão viram **evidência opcional
neutra**; conflito e frequência continuam obrigatórios (medidos).

```
opcional(x) = x.low se x.low + x.high > 0, senão 1
calmo       = min(conflito.low, frequência.low, opcional(desvio), opcional(razão))
R4 = min(calmo, novo)        R5 = min(calmo, conhecido)
```

A ausência é reconhecida pelo formato que já existia (`low + high == 0`), então
nenhuma interface muda e o módulo de otimização herda o comportamento.
Evidência presente entra com a pertinência baixa normal e, se for ruim, barra a
calma. `anomalous` (R2/R3) não muda: só evidência presente acusa anomalia.
Captura em aquecimento ou incompleta continua sem score, porque conflito e
frequência não foram medidos.

### D2. Conflito pesa só no novo quando há reconhecido na disputa

Para cada IP alegado por mais de um MAC: se entre os que alegam há reconhecidos
(`KNOWN`) e não reconhecidos, o conflito daquele IP conta apenas para os não
reconhecidos; os reconhecidos recebem 0 naquele IP. Se todos têm a mesma
reputação, todos recebem `1 - 1/n`, como antes. Reputação `UNKNOWN` ou ausente
conta como não reconhecida. A origem da verdade é o `ReputationProvider` já
injetado.

### D3. Amostra mínima para a razão de replies

`ARP_RATIO_MIN_PACKETS = 4` em `features.py`. Com `requests + replies < 4` na
janela, a razão é `None` e `missing_reasons` recebe
`arp_reply_ratio_insufficient_sample`; zero ARP mantém
`arp_reply_ratio_unavailable`. A frequência continua calculada com qualquer
quantidade de pacotes. A constante é ajustável no ensaio das VMs.

## Alternativas rejeitadas

- **Regra R6 adicional para o conhecido silencioso:** sobrepõe R5, cria mais um
  índice para a otimização e duplica a lógica de calma.
- **Imputar zero ao desvio/razão ausentes:** contradiz o princípio já adotado de
  que ausência não é zero (zero seria uma medição de "sem desvio").
- **Inventário IP→MAC para decidir o dono do IP:** muda o contrato do extrator e
  o banco não guarda IPs.
- **Primeiro dono aprendido do IP:** exige persistência nova, grande demais para o
  prazo; a reputação já injetada resolve o caso do laboratório.

## Consequências

- Gateway e demais conhecidos aparecem confiáveis quando não há sinal ruim,
  antes e durante o ataque; o Atacante segue suspeito.
- A decisão de mitigar (score >= 65, alegação falsa de IP confiável, MAC
  autorizado, duas avaliações) não muda.
- Limite conhecido: com D2, um atacante já reconhecido (`KNOWN`) que alegue o IP
  de outro reconhecido mantém conflito para ambos. É o comportamento
  conservador, documentado, e a promoção a `KNOWN` continua manual (ADR 0004).
- Dispositivo novo e silencioso passa de "sem avaliação" a 50 (desconhecido): é
  a classificação honesta de quem ainda não foi reconhecido.
- Os resultados de otimização publicados antes desta ADR deixam de descrever o
  modelo operacional (ver abaixo).

## Efeito simulado

Valores simulados no motor real (tabela do desenho); não são medições de rede. O "81" vem do ensaio exploratório de 06/10/2026 descrito acima.

| Cenário | Antes | Depois |
|---|---|---|
| Conhecido silencioso, sem baseline | sem avaliação | 16 confiável |
| Gateway com uma resposta ARP | 50 desconhecido | 17 confiável |
| Gateway durante o ataque | 81 suspeito (exploratório) | 20 confiável |
| Conhecido com baseline normal (desvio 0,1) | 50 desconhecido | 20 confiável |
| Conhecido com desvio alto (2,0) | 50 desconhecido | 50 desconhecido |
| Conhecido com 10 ARP/s | 50 desconhecido | 50 desconhecido |
| Novo silencioso | sem avaliação | 50 desconhecido |
| Atacante novo, 10/s | 84 suspeito | 84 suspeito |
| Atacante com gateway alegando junto | 82 suspeito | 82 suspeito |

A validação com kernel e nftables reais em namespaces está no registro
`docs/validation/ensaio-namespaces-2026-10-07.md` (resultado do ensaio
reexecutado com o modelo novo). Ela antecipa, mas não substitui, o ensaio nas quatro VMs.

Métricas internas ([fuzzy-metrics.md](../validation/fuzzy-metrics.md)): 15/15
cenários corretos; só `no_arp_known` mudou (de abstenção para confiável) e a
taxa de abstenção caiu de 0,267 para 0,200.

## Achado do piso 0,5

Com o modelo novo a varredura do piso da razão (0,3 a 0,7) continua apontando
0,5 como o único valor com 15/15; a abstenção agora empata em 0,200 em todos os
pisos. O piso permanece em 0,5, sem alteração nesta mudança.
`RATIO_HIGH_FLOOR` continua sendo um controle, não um ótimo demonstrado (ADR 0011).

## Números novos da pesquisa

O experimento GA/NSGA-II usa o mesmo extrator e as mesmas regras, então foi
refeito. Os resultados anteriores estão em
`research/historical-invalid/v070-pre-adr0013/` e não são comparáveis. Corpus v3:
mesmos 600 cenários (420 benignos, 180 ataques), splits 360/120/120, PCAPs
byte a byte idênticos; só mudaram as entradas extraídas de 77 registros. Foram
20 sementes de GA e 20 de NSGA-II, população 40, 40 gerações.

Teste reservado (120 exemplos), média ± desvio-padrão amostral:

| Método | Precisão | Recall | F1 | FPR | F1 anterior |
|---|---:|---:|---:|---:|---:|
| Manual | 0,6389 | 0,6389 | 0,6389 | 0,1548 | 0,4950 |
| GA | 0,6202 ± 0,0234 | 0,6833 ± 0,0342 | 0,6490 ± 0,0008 | 0,1810 ± 0,0293 | 0,6406 |
| NSGA-II | 0,6154 ± 0,0000 | 0,6667 ± 0,0000 | 0,6400 ± 0,0000 | 0,1786 ± 0,0000 | 0,6321 |

Os 20 genótipos distintos do NSGA-II convergem para a mesma matriz de
confusão no teste (daí o desvio zero): platô de decisão neste conjunto, não
convergência genética nem evidência fora dele.

O que isso significa, sem inflar:

- A maior parte do ganho veio do **modelo**, não do otimizador: o baseline manual
  subiu de 0,4950 para 0,6389 só com a ADR 0013.
- A vantagem de F1 dos otimizadores sobre o manual é marginal: GA +0,0102 e
  NSGA-II +0,0011.
- Ambos trocam mais recall por mais falsos positivos: FPR maior (0,181 e 0,179
  contra 0,155) e precisão menor (0,620 e 0,615 contra 0,639).
- Não se afirma superioridade dos otimizadores. O corpus é sintético, o teste
  tem 120 exemplos, e nada disso foi validado em tráfego real ou nas VMs. O
  classificador operacional continua o manual.

Relatório completo: [research/results/report.md](../../research/results/report.md).
