# ADR 0006 — Dívida técnica: verificação de evidência em Python e JavaScript

Status: duplicação mantida deliberadamente; divergência impedida por corpus compartilhado.
Contexto: dashboard 0.5.0 aprovado. Prioridade atual: ensaio nas quatro VMs.

## Decisão

A regra de interpretação do intervalo de evidência está representada em dois lugares:

- `src/netsentinel/security/evidence.py`, função `verify_interval`: resultado
  formal usado pelo comando de verificação, incluindo `verified` e motivo.
- `src/netsentinel/api/static/core.mjs`, função `counterInterval`: comparação
  dos contadores e mensagem apresentada no dashboard.

Qualquer ajuste futuro no critério de evidência exige revisar e atualizar ambas
as implementações no mesmo PR, com seus testes Python e JavaScript. A revisão
entre integrantes deve conferir a coerência dos resultados e das mensagens.
Não ajustar somente a interface ou somente o verificador sem avaliar o outro.

## Critério compartilhado

Comparar leituras do mesmo agente e MAC alvo, com tempo crescente e contadores
sem reinício. Ambas as leituras devem confirmar mitigação, ARP estático correto
e regra de bloqueio. A evidência exige tráfego ativo e descartes no intervalo
(delta de seen > 0 e dropped > 0), com delta de passed = 0 após o filtro.
Ausência de tráfego não comprova bloqueio. Ping é verificação independente:
a recuperação da conectividade sozinha também não comprova o firewall.

As funções não têm contratos idênticos: o frontend acrescenta tratamento de
leituras ausentes, valores inválidos e mistura de dados simulados/reais, e retorna
mensagem de apresentação em vez do resultado formal `verified`. Essas diferenças
não eliminam a duplicação da regra central nem autorizam presumir equivalência
integral das duas funções.

## Risco e cobertura existente

Uma mudança unilateral pode fazer o dashboard sugerir uma conclusão diferente
da verificação formal. Hoje há testes em `tests/unit/test_security.py` e
`frontend/tests/core.test.mjs`, mas não há uma suíte única que garanta paridade
entre as linguagens. O ensaio real nas VMs continua pendente; os testes offline
não são evidência de execução de nftables no kernel das VMs.

## Evolução possível, após a validação

Se houver tempo após o ensaio, considerar um endpoint autenticado que reutilize
`verify_interval` no backend e exponha o resultado para simples apresentação pelo
frontend. Contrato, tratamento de dados insuficientes e identificação de dados
sintéticos precisam ser definidos antes dessa alteração. Não criar o endpoint
nem refatorar agora; esta ADR registra a dívida, sem ampliar o escopo aprovado.

## Emenda (melhorias 0.7.0)

Endpoint autenticado **rejeitado**. O frontend precisa do veredito de forma
síncrona a cada push de evento. Round-trip por evento adiciona latência e um
modo de falha indefinido: não há resposta definida para o que a interface
mostra quando o endpoint expira. Trocaria uma dívida conhecida por um caminho
de falha desconhecido.

O risco real desta ADR não era duplicação, era **divergência** — e já tinha
ocorrido. `verify_interval` indexava `after['counters'][name]['packets']` e
levantava `KeyError` com contador ausente; `counterInterval` usava
`Number.isFinite` e degradava. A mesma entrada malformada: um estourava, o
outro degradava. `counterInterval` comparava `simulated`; `verify_interval`
não comparava nada equivalente.

Duplicação permanece deliberada. Divergência passa a quebrar o build: o corpus
`tests/fixtures/evidence_cases.json` é lido por `tests/unit/test_evidence_corpus.py`
e por `frontend/tests/evidence-corpus.test.mjs`. `verify_interval` devolve
`reason_code` em todo retorno (a chave `reason` conserva o mesmo valor).
`counterInterval` devolve `{comparable, reason_code, reason, deltas}` — código
para conformidade, texto em português para a tela.
