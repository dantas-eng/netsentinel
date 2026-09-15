# Métricas internas do motor fuzzy

## O que este relatório não afirma

Os cenários são sintéticos e escritos pela equipe. O harness mede
consistência interna e sensibilidade ao limiar da razão de replies,
não acurácia nem taxa de falso positivo em rede real. Apresentar estes
números como acurácia do sistema seria enganoso.

Piso vigente em `RATIO_HIGH_FLOOR`: `0.5`.
Piso recomendado pelo critério (maior `correct`, menor
`abstention_rate`, valor mais alto): `0.5`.

## Matriz de confusão

| esperado \ previsto | confiável | desconhecido | suspeito | abstenção |
| --- | --- | --- | --- | --- |
| confiável | 2 | 0 | 0 | 0 |
| desconhecido | 0 | 6 | 0 | 0 |
| suspeito | 0 | 0 | 3 | 0 |
| abstenção | 0 | 0 | 0 | 4 |

## Por classe

| classe | precision | recall | F1 | support |
| --- | --- | --- | --- | --- |
| confiável | 1.000 | 1.000 | 1.000 | 2 |
| desconhecido | 1.000 | 1.000 | 1.000 | 6 |
| suspeito | 1.000 | 1.000 | 1.000 | 3 |
| abstenção | 1.000 | 1.000 | 1.000 | 4 |

Acertos: 15 / 15.
Taxa de abstenção (previsto nulo): 0.267.

## Erros

Nenhum desacordo entre rótulo esperado e classificação do motor.

## Varredura de `RATIO_HIGH_FLOOR`

| floor | correct | abstention_rate |
| --- | --- | --- |
| 0.3 | 14 | 0.267 |
| 0.4 | 14 | 0.267 |
| 0.5 | 15 | 0.267 |
| 0.6 | 14 | 0.267 |
| 0.7 | 14 | 0.267 |
