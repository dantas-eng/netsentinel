# Validação da extensão — 19/09/2026

- 101 testes Python existentes: passam (`mvp-tests.log`).
- 14 testes Python adicionais: passam, sem skips (`tests.log`). Incluem recomputar todas
  as 40 métricas de teste a partir dos genes salvos e comparar com o baseline original.
- 9 testes JavaScript existentes: passam (`npm test` em frontend).
- Ruff na raiz: passa (`lint.log`).
- 134 arquivos preexistentes em src/tests preservados byte a byte, conforme
  `mvp-sha256.json`; metadados gerados por instalação (.egg-info) não fazem parte da comparação.
- 20 sementes por algoritmo, populações 40, gerações 40, sem reduzir protocolo para entrega.
  Execução real em `run.log`, parâmetros e métricas individuais em `results/results.json`.
- Pareto inspecionado visualmente: 29 pares objetivos não dominados no treino agrupado.
  Teste reservado aparece em painel separado. O gráfico não afirma ótimo global.
- Fontes e parâmetros não foram ajustados em resposta aos resultados de teste. Após a
  execução, a geração do gráfico recebeu apenas deduplicação de pares objetivos para
  acelerar o cálculo da frente agrupada; seleção, inferência e resultados não mudaram.

O cenário novo sem baseline atravessa PCAP, captura, features e estratégia parametrizada
nos testes, e é classificado como suspeito. A paridade de 300 exemplos cobre reputação e
inputs ausentes, conflitos, frequência/desvio acima da saturação e abstenções.

Esta validação é totalmente offline. Não mede captura no VirtualBox, nftables no kernel,
eficácia da mitigação, migração em Postgres ou deploy cloud. Também não certifica qualidade
em tráfego real nem substitui o aceite do professor para a trilha própria.
