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
Repositório público, tag de release e execução de CI no push inicial estão
registrados abaixo. URL de PR com autor e revisor distintos e serviço cloud
implantado continuam pendentes; não se atribuem evidências inexistentes.

A verificação local desta atualização 0.7.0 mediu **148 testes Python**
(`tests/run_offline.py` → `Ran 148 tests`) e **14 testes JavaScript**
(`cd frontend && npm test` → `# pass 14`), com Ruff limpo nos arquivos da
poda. Docker/Postgres/VMs e a checagem visual de CSP/modal na stack em
execução **não foram refeitos** aqui: a imagem em `:8080` estava desatualizada.

## Visão geral

| # | Requisito NEXUS | Situação documentada |
| --- | --- | --- |
| 1 | Open Source Contribution & Collaboration | Repositório público, tag v0.7.0, CI e proteção de branch ativos; ciclo real de PR/code review entre integrantes ainda pendente. |
| 2 | Telecommunications & Network Security | **Código pronto, validação pendente** — ensaio completo nas quatro VMs. |
| 3 | Computational Intelligence & Algorithm Optimization | Implementado e verificado offline; parâmetros experimentais ainda sujeitos à validação nas VMs. |
| 4 | Software Architecture & Design Patterns | Arquitetura documentada, com Observer, Strategy e Repository aplicados e justificados. |
| 5 | Cloud Computing for Software Development | CI público comprovado no GitHub Actions; deploy em nuvem e execução ligada a PR ainda pendentes. |

## 1. Open Source Contribution & Collaboration

**Exigência:** projeto publicado com licença aberta, README, CONTRIBUTING.md e pelo
menos um ciclo real de pull request revisado entre integrantes. O roteiro também
menciona versionamento semântico nas práticas do projeto.

| Evidência disponível | O que demonstra |
| --- | --- |
| [LICENSE](../LICENSE) | Licença MIT para o código do NetSentinel. |
| [README.md](../README.md) | Descrição do projeto, operação, testes, decisões e limites conhecidos. |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Fluxo de branches/PR, revisão por outro integrante e verificações locais/CI. |
| [pyproject.toml](../pyproject.toml) | Versão do pacote declarada como 0.7.0. |
| [Licenças dos assets](../src/netsentinel/api/static/vendor/licenses/) | Avisos dos componentes de terceiros distribuídos com o dashboard offline. |
| https://github.com/dantas-eng/netsentinel | Repositório público do projeto (conta `dantas-eng`). |
| Tag `v0.7.0` → commit `88ca038` | Release anotada da versão avaliada (merge `feat/melhorias-0.7.0` em `main`). |
| https://github.com/dantas-eng/netsentinel/actions/runs/35162443539 | CI verde no push inicial: Ruff, 148 testes Python, 14 testes JS, container/Postgres. |
| Proteção de `main` | PR obrigatório, 1 review, checks `Lint e testes offline`, `Frontend offline` e `Container e Postgres sintéticos`. |

**Limite:** publicação e CI não substituem review entre integrantes. Não há nesta
documentação PR fictício nem aprovação inventada.

**Para fechar:** registrar URL de pelo menos um PR com autor e revisor distintos do
grupo, comentários ou aprovação de review e desfecho verificável. Conservar o
histórico.

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

**Exigência:** aplicar algoritmo bioinspirado ou metaheurística para otimização ou
classificação real no sistema. Lógica fuzzy está explicitamente entre as opções
do roteiro; não é necessário introduzir algoritmo genético para justificar esta escolha.

| Evidência concreta | O que demonstra |
| --- | --- |
| [analysis/features.py](../src/netsentinel/analysis/features.py) | Extrai conflito ARP, frequência, reputação, desvio de volume e `arp_reply_ratio` por dispositivo. |
| [fuzzy/membership.py](../src/netsentinel/analysis/fuzzy/membership.py), [rules.py](../src/netsentinel/analysis/fuzzy/rules.py) e [engine.py](../src/netsentinel/analysis/fuzzy/engine.py) | Cinco regras Mamdani, operações min/max e defuzzificação por centroide com scikit-fuzzy. Score 0–100, limiares 35/65. |
| [analysis/contracts.py](../src/netsentinel/analysis/contracts.py) e [services/pipeline.py](../src/netsentinel/services/pipeline.py) | Providers injetados de reputação/baseline e uso da estratégia no fluxo efetivo do backend. |
| [test_fuzzy.py](../tests/unit/test_fuzzy.py), `RuleTests.test_each_rule_in_isolation`, `InferenceTests.test_r2_survives_missing_baseline` e `test_no_evidence_abstains_after_rules` | Regras exercitadas, classificação possível sem baseline e abstenção somente quando nenhuma regra dispara. |
| [test_fuzzy_demo.py](../tests/integration/test_fuzzy_demo.py), `DemoAcceptance.test_new_attacker_without_baseline_with_conflict` e `test_new_attacker_without_baseline_without_conflict` | PCAP sintético → captura → classificação do Atacante NEW sem baseline como suspeito, inclusive sem conflito observado. |
| [test_repository.py](../tests/unit/test_repository.py), `RepositoryTests.test_baseline_converts_each_window_bytes_to_bytes_per_second` | Cinco janelas com 80/160/240/320/400 bytes resultam em mediana de 30 bytes/s, respeitando a unidade do provider. |
| [docs/validation/fuzzy-metrics.md](validation/fuzzy-metrics.md), gerado por [tools/fuzzy_metrics.py](../tools/fuzzy_metrics.py) | Consistência interna em 15 cenários sintéticos escritos pela equipe; `RATIO_HIGH_FLOOR=0.5` é o único piso com 15/15. **Não é acurácia nem taxa de falso positivo em rede real.** |

Decisões relacionadas: [ADR 0002](decisions/0002-reputacao-e-janela-demo.md),
[ADR 0004](decisions/0004-promocao-manual-de-reputacao.md) e
[ADR 0005](decisions/0005-baseline-persistido-e-migracoes.md).

**Alcance:** a inferência classifica dados derivados de pacotes, com providers reais
na integração; não é apenas uma tela exibindo scores fixos. Isso não comprova
acurácia, generalização ou taxa de falsos positivos em redes reais. Funções de
pertinência e regras são parâmetros experimentais aprovados; medir frequência real
e comportamento das janelas no ensaio. GA e ajuste evolutivo continuam fora do MVP.

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

**Situação: código pronto, validação pendente.** Essa expressão descreve a aplicação,
containerização e configuração de CI disponíveis; **não significa que publicação/CD
em Cloud Run já estejam implementados ou que exista um serviço público implantado**.
O deploy e sua configuração final ainda precisam ser realizados e comprovados.

| Evidência concreta | Alcance e limite |
| --- | --- |
| [Dockerfile](../Dockerfile) e [frontend/build.mjs](../frontend/build.mjs) | Build multi-stage de frontend e Python, com assets locais e runtime Linux. Imagem ainda não executada neste ambiente. |
| [docker-compose.yml](../docker-compose.yml) | Serviço sintético local e Postgres persistente. Compose local não equivale a cloud. |
| [deploy/start-container.sh](../deploy/start-container.sh), [api/wsgi.py](../src/netsentinel/api/wsgi.py) e [settings.py](../src/netsentinel/api/settings.py) | Migração antes do servidor, Gunicorn com um worker, PORT configurável, fonte sintética e exigência de Postgres no modo cloud. |
| [migrations/](../migrations/) e [repositories/migrate.py](../src/netsentinel/repositories/migrate.py) | Schema versionado com Alembic. |
| [test_repository.py](../tests/unit/test_repository.py), `RepositoryTests.test_migrations_match_models_and_repeat_without_changes` e `test_initial_migration_compiles_for_postgres_without_a_live_database` | Migração exercitada em SQLite e compilação SQL para Postgres; não comprovam execução em Postgres real. |
| [.github/workflows/ci.yml](../.github/workflows/ci.yml) | Gatilho pull_request e push em main; execução pública verde em https://github.com/dantas-eng/netsentinel/actions/runs/35162443539 (push inicial). Execução ligada a PR ainda pendente. |
| [tests/container_smoke.py](../tests/container_smoke.py) | Teste HTTP preparado para o Compose, com sessão/CSRF e dados sintéticos. Não executado nesta entrega; não testa política de cookies do browser. |

Roteiros: [docs/docker.md](docker.md) e [docs/backend.md](backend.md).

**Para fechar:** executar e registrar build/Compose e migração em Postgres real;
concluir deploy em GCP Cloud Run com Postgres gerenciado e HTTPS; registrar URL e
revisão/commit implantados; publicar o repositório e uma execução de Actions ligada
a PR com lint/testes; configurar e demonstrar o fluxo de publicação/CD. Registrar
as evidências sem credenciais. O ambiente cloud usa dados sintéticos e não se conecta
à rede isolada do ataque, conforme a separação já aprovada.

## Condição de atualização deste mapa

Trocar o estado de um requisito somente após anexar referência verificável à sua
evidência: arquivo de ensaio, saída de teste real ou URL pública, com versão/commit
e contexto de execução. Falta de erro relatado não é resultado de teste.

Este mapa não substitui vídeo pitch de até três minutos, apresentação individual
nem comprovação de equipe/inscrição previstos no regulamento. Não foram produzidos
ou comprovados por esta etapa documental. A eventual janela de ajustes após a
avaliação continua dependente de esclarecimento do professor; não pressupor essa
janela para fechar as pendências.
