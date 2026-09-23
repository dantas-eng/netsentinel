# Integração local 0.7.0 + otimização — validação

## Origem e preservação

Base: `netsentinel-main.zip` recebido do grupo, sem histórico Git comprovado.
Os 110 arquivos sob src/ existentes no ZIP permanecem byte a byte iguais,
inclusive assets recompilados. Segurança, API e dashboard preservados.
Extensão de otimização adicionada; sem quinto gene. A quinta feature ratio tem
rampa fixa importada do fuzzy 0.7.0. ADR 0009 preserva a origem da extensão;
ADR 0010 registra decisões e limites da integração.

Os 600 hashes PCAP, IDs, rótulos e splits coincidem com o experimento 0.6.0.
Somente as features são reextraídas pela base 0.7.0. Todo o corpus tem ratio=1;
isso limita a comparação e é destacado no relatório atual. Resultados e logs
históricos ficam em historical-v060/; eles não validam o baseline 0.7.0.

## Verificações

- Base: 148 testes Python, `python tests/run_offline.py`.
- Otimização: 14 testes, todos passando sem skips, `python -m unittest discover -s research/tests -v`.
- Frontend: 14 testes JS, `npm test` em frontend.
- Ruff na árvore completa e build do frontend.
- Paridade com o fuzzy manual atual em 300 casos incluindo ratio ausente,
  zero, piso, teto e intermediários. Ratio alto sozinho ativa R2.
- PCAP → captura → features → estratégia; novas features não são inventadas
  ao carregar manifestos antigos: load rejeita manifesto sem arp_reply_ratio.
- Resultados de 20 sementes de cada algoritmo, com mesmos hiperparâmetros,
  reavaliados e confrontados pelos testes com as métricas salvas.

Saídas: mvp-tests.log, tests.log, lint.log, frontend-build.log, run.log.
Integridade de arquivos e corpus: merge-integrity.json. CI remota, VMs,
Docker/Postgres real e cloud não foram executados nesta integração.

A configuração de CI permanece disponível, mas não é apresentada como execução
ativa ou aprovada no GitHub. Os testes opcionais da otimização são executados
separadamente pelos comandos do research/README.md.

Resultado atual: manual, AG e NSGA-II empatam em F1=0,5133 no teste.
Frente empírica agrupada de treino: quatro pontos objetivos distintos.
As 40 execuções foram efetivamente realizadas; nenhuma melhora é presumida.
