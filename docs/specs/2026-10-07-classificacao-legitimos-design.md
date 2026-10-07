# Classificação de dispositivos legítimos — design

Data: 07/10/2026. Base: main 8ec1f74 (0.7.0 + preparação de fechamento).

## Problema

Ensaio com kernel, Scapy e nftables reais em quatro namespaces de rede
(gateway, Vítima, Atacante e Sensor numa bridge em modo hub) mostrou que a
detecção e a mitigação do Atacante funcionam, mas a classificação dos
dispositivos legítimos é enganosa:

1. **Gateway marcado como suspeito (81) durante o ataque.** O conflito
   (`1 - 1/n` por IP) pune todos os MACs que alegam o IP disputado, inclusive
   o dono legítimo.
2. **Legítimos nunca chegam a confiável.** R5 exige razão ARP baixa e desvio
   baixo. Sem ARP na janela ou sem baseline, ambos ficam com pertinências zero
   e R5 não dispara: o dispositivo fica sem avaliação ou em 50 (desconhecido).
3. **Uma resposta ARP normal vira anomalia.** Com uma única resposta na janela,
   a razão de replies é 1, `ratio_high` = 1 e R3 leva o gateway a 50.

## Objetivo e critério de sucesso

O painel deve mostrar a rede como ela é: dispositivo reconhecido e sem sinal
ruim aparece confiável; o dono legítimo de um IP disputado não é penalizado; a
detecção do Atacante não muda.

Sucesso, verificado no ensaio em namespaces: gateway, Vítima e Sensor com
classificação `confiável` antes e durante o ataque; Atacante `suspeito`;
mitigação aplicada; ping volta. As fixtures de aceitação mantêm 82,38 e 84,44.

## Decisões (aprovadas pelo grupo)

### D1. Conhecido e silencioso é confiável

Ausência de ARP na janela passa a significar "nada suspeito medido", não "falta
de prova". Implementação por **evidência opcional neutra** nas regras R4 e R5:

- Conflito e frequência continuam **obrigatórios** (medidos).
- Desvio e razão são **evidência opcional**: ausentes, não pesam contra a calma;
  presentes, entram com a pertinência baixa normal.
- A ausência é reconhecida pelo formato já existente: `low + high == 0`. Nenhuma
  interface muda e o módulo de otimização herda o comportamento.
- `anomalous` (R2/R3) não muda: só evidência presente acusa anomalia.

```
opcional(x) = x.low se x.low + x.high > 0, senão 1
calmo       = min(conflito.low, frequência.low, opcional(desvio), opcional(razão))
R4 = min(calmo, novo)        R5 = min(calmo, conhecido)
```

Rejeitadas: regra R6 adicional (sobreposição com R5, mais índices na
otimização) e imputar zero na ausência (contradiz "ausência não é zero").

### D2. Conflito pesa só no novo quando há reconhecido na disputa

Para cada IP alegado por mais de um MAC: se entre os MACs que alegam há
reconhecidos (`KNOWN`) e não reconhecidos, o conflito daquele IP conta apenas
para os não reconhecidos; os reconhecidos recebem 0 naquele IP. Se todos os
envolvidos têm a mesma reputação, todos recebem `1 - 1/n`, como hoje.
Reputação `UNKNOWN`/ausente conta como não reconhecida.

A origem da verdade é o `ReputationProvider` já injetado. Rejeitadas:
inventário IP→MAC (muda contrato do extrator, banco não guarda IPs) e primeiro
dono aprendido (persistência nova, grande para o prazo).

### D3. Amostra mínima para a razão de replies

`ARP_RATIO_MIN_PACKETS = 4` em `features.py`. Com `requests + replies < 4` na
janela, a razão é `None` e `missing_reasons` recebe
`arp_reply_ratio_insufficient_sample`. Zero ARP mantém
`arp_reply_ratio_unavailable`. A frequência continua calculada com qualquer
quantidade. A constante é ajustável no ensaio das VMs.

## Efeito esperado (simulado no motor real)

| Cenário | Antes | Depois |
|---|---|---|
| Conhecido silencioso, sem baseline | sem avaliação | 16 confiável |
| Gateway com uma resposta ARP | 50 desconhecido | 17 confiável |
| Gateway durante o ataque | 81 suspeito (ensaio) | 20 confiável |
| Conhecido com baseline normal (desvio 0,1) | 50 desconhecido | 20 confiável |
| Conhecido com desvio alto (2,0) | 50 desconhecido | 50 desconhecido |
| Conhecido com 10 ARP/s | 50 desconhecido | 50 desconhecido |
| Novo silencioso | sem avaliação | 50 desconhecido |
| Atacante novo, 10/s | 84 suspeito | 84 suspeito |
| Atacante com gateway alegando junto | 82 suspeito | 82 suspeito |

Inalterado: captura em aquecimento ou incompleta continua sem score (conflito e
frequência não medidos); a decisão de mitigar (score ≥ 65, alegação falsa,
MAC autorizado, duas avaliações) não muda.

## Pesquisa de otimização

O experimento GA/NSGA-II usa o mesmo `FeatureExtractor` e as mesmas regras, e o
corpus guarda inputs já extraídos. Os resultados publicados deixam de descrever
o modelo operacional. Procedimento:

1. Arquivar `research/results` atual em `research/historical-invalid/` com nota.
2. Regerar o corpus (v3) com os mesmos cenários e sementes.
3. Reexecutar 20 sementes GA e 20 NSGA-II com o mesmo protocolo.
4. Reexecutar `tools/fuzzy_metrics.py`; se o piso 0,5 deixar de ser o melhor,
   registrar o resultado sem alterar o piso nesta mudança.
5. Reportar os números como saírem, inclusive se o F1 cair.

## Testes

- Unitários novos: conflito reconhecido × novo, reconhecidos × reconhecidos,
  `UNKNOWN` × reconhecido; amostra 3 e 4 pacotes; conhecido silencioso
  confiável; novo silencioso desconhecido; aquecimento sem score; razão presente
  e alta continua anômala.
- Testes existentes que esperam ausência de score para dado opcional ausente
  são atualizados citando a ADR 0013.
- Fixtures PCAP de aceitação mantêm os scores documentados.
- Suítes completas: `tests/run_offline.py`, `research.tests`, `ruff`, frontend.

## Documentação

ADR 0013; `docs/fuzzy.md` (regras e ausência de dados);
`docs/validation/fuzzy-metrics.md`; `docs/compliance.md` (números do requisito 3);
`docs/closure/presentation.md` (perguntas 8 e 15, trecho do pitch);
`research/README.md` e `research/VALIDATION.md`; `CHANGELOG.md`.

## Validação real

Repetir o ensaio em namespaces com o código novo. Registrar linha do tempo por
dispositivo, ping, estado ARP e contadores. Isso antecipa, mas não substitui, o
ensaio nas quatro VMs exigido pelo roteiro.

## Fora do escopo

Painel de pacotes estilo Wireshark (frente B), mudanças de interface do
dashboard, mudança da regra de mitigação, novos genes de otimização.

## Riscos

- Tempo do experimento desconhecido: medir no início e avisar se passar de 1 h.
- F1 pode cair com o modelo novo; o relatório registra o resultado real.
- Com D2, um atacante já reconhecido que alegue o IP de outro reconhecido segue
  com conflito para ambos; é o comportamento conservador documentado.
