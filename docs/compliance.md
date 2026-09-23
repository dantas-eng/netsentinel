# NetSentinel — mapa de conformidade NEXUS

Base de implementação: versão 0.7.0. Este documento registra evidências disponíveis,
o alcance de cada evidência e o que ainda falta demonstrar. Não é declaração de
aprovação pela banca nem de conclusão integral dos cinco requisitos.

## Fontes e critério de leitura

Fonte normativa dos cinco requisitos: **16_NEXUS_6-8Sem_ECO.pdf**, página 1,
seção “Requisitos do Projeto”. O **Regulamento_Geral_ExpoTech_2026-2.pdf** complementa
a leitura, especialmente itens 7 (entregas), 8 (avaliação) e 9 (proibições).
Os PDFs oficiais prevalecem sobre o guia interno e esta interpretação operacional.

Um arquivo comprova implementação ou intenção documentada; um teste offline
comprova somente o comportamento exercitado no seu ambiente. Código de teste
escrito para Docker/Postgres não comprova que esse teste já tenha sido executado.
Nesta auditoria, o repositório GitHub, a tag `v0.7.0`, o PR #3, a revisão e a execução
dos checks de CI foram comprovados. A proteção da branch ainda não foi comprovada.
A validação local da extensão de otimização está em `research/VALIDATION.md`;
Docker, Postgres real, VMs, tráfego real e deploy em nuvem continuam dependendo de
evidência de execução correspondente.

## Visão geral

| # | Requisito NEXUS | Situação documentada |
| --- | --- | --- |
| 1 | Open Source Contribution & Collaboration | **Parcialmente comprovado** — repositório GitHub, licença, documentação, tag v0.7.0, PR real, revisão e execução de CI já comprovados; proteção da branch ainda não comprovada. |
| 2 | Telecommunications & Network Security | **Código pronto, validação pendente** — ensaio completo nas quatro VMs. |
| 3 | Computational Intelligence & Algorithm Optimization | **Implementado e verificado offline** — classificador fuzzy operacional mantido; extensão GA/NSGA-II validada por testes e experimento reprodutível; tráfego real, VMs e aceitação da trilha ainda pendentes. |
| 4 | Software Architecture & Design Patterns | Arquitetura documentada, com Observer, Strategy e Repository aplicados e justificados. |
| 5 | Cloud Computing for Software Development | **Parcialmente comprovado** — workflow de CI disponível e execução em PR comprovada; deploy em nuvem e fluxo de CD ainda pendentes. |

## 1. Open Source Contribution & Collaboration

**Situação: parcialmente comprovado.** O repositório está publicado no GitHub e
já existe evidência de versionamento, documentação, tag, pull request revisado e
execução da CI. A proteção da branch ainda não foi comprovada nesta auditoria.

**Exigência:** projeto publicado com licença aberta, README, CONTRIBUTING.md e pelo
menos um ciclo real de pull request revisado entre integrantes. O roteiro também
menciona versionamento semântico nas práticas do projeto.

| Evidência concreta | O que demonstra |
| --- | --- |
| [Repositório GitHub](https://github.com/dantas-eng/netsentinel) | Repositório do projeto `dantas-eng/netsentinel`. |
| [LICENSE](../LICENSE) | Licença MIT para o código do NetSentinel. |
| [README.md](../README.md) | Descrição do projeto, instalação, operação, testes e índice da documentação. |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Fluxo de branches/PR, revisão por outro integrante e verificações locais/CI. |
| [pyproject.toml](../pyproject.toml) | Versão do pacote declarada como 0.7.0. |
| Tag `v0.7.0` no remoto `origin` | Versionamento da entrega publicado no repositório remoto. |
| PR #3 `docs: update validation evidence README` | Ciclo real de pull request com revisão por integrante distinto do autor e merge na `main`. |
| Checks do PR #3 | Execução remota da CI associada ao pull request, com os três checks concluídos com sucesso. |
| [Licenças dos assets](../src/netsentinel/api/static/vendor/licenses/) | Avisos dos componentes de terceiros distribuídos com o dashboard offline. |

**Limites:** a proteção da branch `main` não foi comprovada nesta auditoria.
A existência da configuração de CI e a execução da CI no PR comprovam o fluxo de
integração contínua exercitado, mas não comprovam proteção de branch nem práticas
que não tenham evidência correspondente.

**Para fechar:** registrar evidência verificável da proteção da branch, caso ela
seja exigida para a entrega. Conservar URL do repositório, tag, PR, revisão e
checks associados ao ciclo real.

## 2. Telecommunications & Network Security

**Situação: código pronto, validação pendente.** O monitoramento e o cenário de
identificação/mitigação estão implementados; a vulnerabilidade ainda precisa ser
demonstrada e mitigada no ambiente real das quatro VMs.

| Evidência concreta | Alcance |
| --- | --- |
| [capture/service.py](../src/netsentinel/capture/service.py), [scapy_source.py](../src/netsentinel/capture/scapy_source.py) e [normalizer.py](../src/netsentinel/capture/normalizer.py) | Captura Scapy, modo promíscuo, agregação e separação entre origem Ethernet observada e alegação ARP. |
| [test_capture.py](../tests/unit/test_capture.py), `CaptureTests.test_preserves_claim_and_actual_source` e `test_promiscuous_persistent_socket` | Preservação de autoria observada e configuração do socket; não comprovam visibilidade unicast no VirtualBox. |
| [attack.py](../src/netsentinel/security/attack.py), [config.py](../src/netsentinel/security/config.py) e [system.py](../src/netsentinel/security/system.py) | Ataque limitado ao alvo configurado, sem encaminhamento, e verificações locais de isolamento. |
| [demo.py](../src/netsentinel/security/demo.py), `SecurityDemo.consume` | Detecta qualquer MAC com score >=65 e falsificação de um IP em `trusted_bindings()`; a mitigação continua exclusiva do MAC pré-aprovado (ADR 0008). Sequência ADR 0007 por MAC. |
| [strategy.py](../src/netsentinel/security/strategy.py) e [agente da Vítima](../src/netsentinel/security/agent/) | Comunicação pela Internal Network; aplicação idempotente de ARP estático e firewall netdev/ingress, validação de MAC e ações fixas. |
| [evidence.py](../src/netsentinel/security/evidence.py), `verify_interval` | Verifica deltas de contadores, estado ARP e bloqueio; não declara ping verificado. |
| [test_security_pipeline.py](../tests/integration/test_security_pipeline.py), `SecurityPipelineAcceptance.test_new_attacker_without_baseline_causes_verified_agent_action` | PCAP → captura → fuzzy → Strategy → API do agente, com kernel/HTTP de transporte substituídos nos testes. |
| [test_security.py](../tests/unit/test_security.py), `EvidenceTests.test_active_drops_and_zero_post_filter_delta` e `test_ping_or_static_alone_cannot_prove_firewall` | Critério de evidência e rejeição de comprovação incompleta, com dados controlados. |
| [test_security_consecutive.py](../tests/unit/test_security_consecutive.py), `ConsecutiveEvaluationsTests.test_two_consecutive_qualifications_apply_once_at_threshold` e `test_nonqualifying_evaluation_resets_then_requires_two_fresh_ones` | Disparo na segunda avaliação e reinício da sequência. |

Decisões relacionadas: [ADR 0001](decisions/0001-arp-sem-encaminhamento.md),
[ADR 0003](decisions/0003-agente-e-acesso-hostonly.md),
[ADR 0007](decisions/0007-duas-avaliacoes-antes-da-mitigacao.md) e
[ADR 0008](decisions/0008-deteccao-ampla-mitigacao-restrita.md).
Roteiro operacional: [lab/README.md](../lab/README.md).

A detecção 0.7.0 é mais ampla (segundo atacante sintético, falsificação de
qualquer papel em `trusted_bindings()`, evento `threat_unmitigable`). **O
status deste requisito não muda:** a vulnerabilidade ainda exige as quatro
VMs, ping caindo/voltando e nftables no kernel.

**Para fechar:** reunir captura que confirme visibilidade unicast no Sensor,
registros do ataque sem forwarding, queda/recuperação do ping Vítima → Gateway,
ARP permanente correto e leituras comparáveis com deltas positivos de vistos e
descartados e delta zero de passagem após o filtro. Associar os registros ao mesmo
ensaio/versão e identificar leituras anteriores/posteriores. Confirmar login e
dashboard pelo Host-only. A captura no Sensor pode continuar vendo pacotes que o
firewall descarta na Vítima; isso não contradiz o critério pós-filtro.

Nenhum desses testes autoriza uso em redes de terceiros. Duas avaliações podem
usar janelas sobrepostas e não garantem perda perceptível de ping. A confirmação
visual e o funcionamento do nftables no kernel continuam pendentes.

## 3. Computational Intelligence & Algorithm Optimization

**Situação: implementado e verificado offline; validação em tráfego/VM real pendente.** O classificador fuzzy 0.7.0 continua sendo a estratégia operacional manual do sistema. A extensão AG/NSGA-II foi implementada em `optimization/` para otimização offline dos parâmetros do classificador, sem substituição automática da estratégia operacional.

**Exigência:** aplicar algoritmo bioinspirado ou metaheurística para otimização ou classificação. A extensão utiliza Algoritmo Genético (GA) e NSGA-II para otimizar os parâmetros do classificador fuzzy.

| Evidência concreta | O que demonstra |
| --- | --- |
| [optimization/classifier.py](../src/netsentinel/optimization/classifier.py) | Estratégia fuzzy parametrizada para avaliar candidatos sem alterar o classificador operacional. |
| [optimization/experiment.py](../src/netsentinel/optimization/experiment.py) | Execução dos experimentos GA e NSGA-II, com seleção baseada na validação e teste reservado. |
| [optimization/dataset.py](../src/netsentinel/optimization/dataset.py) | Geração e particionamento estratificado do corpus sintético utilizado no experimento. |
| [optimization/diagnostics.py](../src/netsentinel/optimization/diagnostics.py) | Diagnósticos de cobertura e variação do corpus antes da avaliação. |
| [research/tests/test_optimization.py](../research/tests/test_optimization.py) | 18 testes da extensão de otimização executados com sucesso. |
| [ADR 0009](decisions/0009-otimizacao-evolutiva-offline.md) | Define escopo, genes, protocolo experimental, critérios de seleção e limites da extensão offline. |
| [ADR 0011](decisions/0011-corpus-arp-variavel-e-validade-experimental.md) | Documenta a correção do corpus de ARP e invalida as comparações históricas com ratio constante. |
| [research/results/report.md](../research/results/report.md) | Relatório consolidado dos experimentos, métricas, dispersão entre sementes e limitações. |
| [research/results/results.json](../research/results/results.json) | Resultados estruturados das 20 execuções GA e 20 execuções NSGA-II. |
| [research/results/diagnostics.json](../research/results/diagnostics.json) | Metadados e diagnósticos do corpus utilizado na avaliação oficial. |
| [research/VALIDATION.md](../research/VALIDATION.md) | Registro do protocolo, testes, reprodução e limites conhecidos da validação. |

**Protocolo verificado:** foram avaliados 600 cenários sintéticos independentes, sendo 420 benignos e 180 ataques, com separação fixa em 360 exemplos de treino, 120 de validação e 120 de teste. Cada cenário permanece integralmente em uma única divisão. GA e NSGA-II foram executados em 20 sementes cada, totalizando 40 execuções, com população de 40 indivíduos e 40 gerações. O conjunto de teste não foi usado para otimização ou seleção dos parâmetros.

**Reprodução:** uma execução independente reproduziu exatamente as 40 soluções selecionadas e suas métricas de validação/teste. As seis diferenças encontradas ficaram restritas ao `training_archive`; os objetos lógicos do dataset foram idênticos, com diferença de SHA explicada pela serialização JSON.

**Resultados documentados:** no split sintético reservado, o baseline manual apresentou F1 de 0.4950; GA apresentou F1 médio de 0.6406 e NSGA-II de 0.6321. Esses números descrevem este experimento e não constituem garantia de superioridade em tráfego real. As métricas incluem precisão, recall, F1 e FPR, com abstenções tratadas separadamente e sem remoção do denominador.

**Limites:** o corpus é sintético e a validação foi offline. Não há ainda validação em tráfego real, ensaio completo nas VMs, adoção operacional dos parâmetros otimizados ou conclusão de eficácia de defesa em ambiente real. A aceitação da trilha pelo professor e os ensaios de VM permanecem pendentes. A antiga ADR 0010 é histórica e não deve ser usada como fonte do protocolo experimental atual.

**Base operacional relacionada:** [analysis/features.py](../src/netsentinel/analysis/features.py), [fuzzy/membership.py](../src/netsentinel/analysis/fuzzy/membership.py), [fuzzy/rules.py](../src/netsentinel/analysis/fuzzy/rules.py), [fuzzy/engine.py](../src/netsentinel/analysis/fuzzy/engine.py) e [services/pipeline.py](../src/netsentinel/services/pipeline.py) permanecem como a implementação operacional do classificador fuzzy 0.7.0.

## 4. Software Architecture & Design Patterns

**Exigência:** arquitetura documentada com padrões efetivamente aplicados e justificados.

Documento principal: **[Arquitetura e padrões](architecture/overview.md)**, com
visão textual/diagrama das camadas, responsabilidades e ordem real de execução.

| Padrão | Implementação e justificativa rastreável | Evidência de integração |
| --- | --- | --- |
| Observer | [events/bus.py](../src/netsentinel/events/bus.py), `EventBus`, publica para assinantes; [api/app.py](../src/netsentinel/api/app.py), `notify`, adapta eventos a Socket.IO. Separa produção de eventos da entrega ao dashboard. | [test_backend.py](../tests/integration/test_backend.py), `BackendTests.test_websocket_requires_session_and_csrf_then_receives_persisted_events`. |
| Strategy | [analysis/contracts.py](../src/netsentinel/analysis/contracts.py), `ClassificationStrategy`, e [security/strategy.py](../src/netsentinel/security/strategy.py), `MitigationStrategy`; implementações fuzzy, agente real e [mitigação sintética](../src/netsentinel/services/synthetic.py). Isola algoritmo e mecanismo de defesa de seus consumidores. Identidade de mitigação formalizada em [SecurityIdentity](../src/netsentinel/security/identity.py) (`attacker_mac` + `trusted_bindings()`). | `BackendTests.test_cloud_uses_secure_cookie_and_never_constructs_real_agent` e `test_pcap_to_repository_strategy_agent_and_websocket` no mesmo arquivo de testes. |
| Repository | [repositories/store.py](../src/netsentinel/repositories/store.py), `Repository`, concentra persistência e fornece reputação/baseline ao fuzzy. Isola análise das consultas e das regras de armazenamento. | [test_repository.py](../tests/unit/test_repository.py), `RepositoryTests.test_new_stays_new_after_persisting_and_restart` e `test_confirmation_persists_and_revocation_is_not_overwritten_by_bootstrap`. |

A dívida da [ADR 0006](decisions/0006-duplicacao-da-verificacao-de-evidencia.md)
não foi “resolvida” criando um endpoint: a emenda 0.7.0 **rejeita** o endpoint
autenticado e impede divergência com o corpus
[evidence_cases.json](../tests/fixtures/evidence_cases.json), lido por
`test_evidence_corpus.py` e `frontend/tests/evidence-corpus.test.mjs`.
`verify_interval` e `counterInterval` passam a expor `reason_code` no mesmo
vocabulário. Duplicação permanece deliberada.

**Alcance:** os padrões estão vinculados a classes, contratos e chamadas existentes.
A documentação não promete arquitetura distribuída nem múltiplos workers; fonte e
EventBus são locais ao processo. O integrante deve explicar por que cada padrão é
usado, suas limitações e como a composição ocorre, não apenas citar os nomes.

## 5. Cloud Computing for Software Development

**Situação: parcialmente comprovado.** O workflow de CI está versionado e houve
execução real associada ao PR #3. O deploy em nuvem e o fluxo de CD ainda não foram
comprovados nesta auditoria.

**Exigência:** desenvolvimento com serviços de nuvem e integração/entrega contínua
automatizada, conforme o requisito NEXUS.

| Evidência concreta | O que demonstra |
| --- | --- |
| [.github/workflows/ci.yml](../.github/workflows/ci.yml) | Workflow versionado com gatilhos para pull request, push na `main` e execução manual. |
| Checks do PR #3 | Execução remota da CI associada a um pull request real, com os três checks concluídos com sucesso. |
| [docker-compose.yml](../docker-compose.yml) | Ambiente local com aplicação e Postgres para validação integrada. |
| [tests/container_smoke.py](../tests/container_smoke.py) | Teste HTTP sobre o Compose, com sessão/CSRF e dados sintéticos. |

**Limites:** a existência do workflow e a execução do PR comprovam CI exercitada,
mas não comprovam deploy em provedor de nuvem, fluxo de CD, Postgres gerenciado ou
execução do ambiente em VMs.

**Para fechar:** registrar evidência do deploy em nuvem e do fluxo de CD, caso
esses itens sejam exigidos para a entrega, além de conservar os resultados dos
ensaios de container/Postgres quando executados no ambiente correspondente.
## Condição de atualização deste mapa

Trocar o estado de um requisito somente após anexar referência verificável à sua
evidência: arquivo de ensaio, saída de teste real ou URL pública, com versão/commit
e contexto de execução. Falta de erro relatado não é resultado de teste.

Este mapa não substitui vídeo pitch de até três minutos, apresentação individual
nem comprovação de equipe/inscrição previstos no regulamento. Não foram produzidos
ou comprovados por esta etapa documental. A eventual janela de ajustes após a
avaliação continua dependente de esclarecimento do professor; não pressupor essa
janela para fechar as pendências.
