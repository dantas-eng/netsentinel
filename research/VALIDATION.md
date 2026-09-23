# Validação do corpus v2 e correção experimental

## Antes de qualquer comparação

Os PCAPs foram regenerados com requests/replies reais. diagnostics.json foi obtido
antes da decisão da ADR 0011 e antes das 40 execuções. Não houve seleção do piso
ratio por F1 do teste. Foram confirmados 219 ratios distintos, variação por família
e por classe, e influência dos quatro genes nas decisões de treino.

R4 não é apresentada como coberta pelo dataset: NEW sem baseline impede confirmar
desvio baixo. R5 voltou a disparar. As cinco regras continuam nos testes isolados
do fuzzy; não se inventou baseline para criar ativação artificial de R4.

## Regressão e testes novos

- 148 testes Python da base 0.7.0, sem edição dos módulos operacionais.
- 18 testes da extensão: paridade com o baseline, corpus/splits, requests op=1 e
  replies op=2 no PCAP relido, razão/contagens reais, variação em cada família,
  sensibilidade por gene, rejeição de corpus degenerado/manifesto antigo,
  ausência de histórico e reprodução das métricas das 40 execuções.
- 14 testes JavaScript existentes.
- Ruff na árvore completa.

Logs: mvp-tests.log, tests.log, frontend-tests.log, lint.log e run.log.
A verificação final da extensão inclui todas as 40 métricas salvas e baseline,
recalculados usando as configurações escolhidas e o teste reservado.

## Preservação e limites

integrity.json registra a preservação dos 110 arquivos src/assets da base 0.7.0.
Os 600 IDs, contextos originais, rótulos e splits foram mantidos; acrescentou-se
mistura de opcodes com RNG separado. Os PCAPs e features derivados mudam como
esperado. As duas comparações invalidadas foram conservadas byte a byte, com
hashes de cada arquivo, sob historical-invalid/.

Nenhum hiperparâmetro de AG/NSGA-II foi alterado. São 20 sementes por método,
população 40, 40 gerações, quatro genes; piso ratio fixo em 0,5. Os novos resultados
não devem ser comparados numericamente aos históricos como se o corpus fosse o
mesmo. A prevenção de degeneração não comprova generalização a redes reais.

Não houve execução de VMs, Docker/Postgres real, CI remota ou deploy cloud.
Não houve criação/publicação de repositório. A aplicação continua usando o fuzzy
manual, e o aceite docente da trilha própria permanece pendente.
