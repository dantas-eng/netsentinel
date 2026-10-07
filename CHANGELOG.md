# Changelog

Versionamento semântico. As entregas anteriores à 0.4.0 cobriram captura,
normalização, janela móvel e o motor fuzzy.

## Não lançado — classificação de legítimos (07/10/2026)

- ADR 0013: conflito pesa só no não reconhecido quando há reconhecido na disputa
  (gateway deixa de ficar suspeito durante o ataque); desvio e razão ausentes são
  neutros em R4/R5 (conhecido silencioso é confiável); razão de replies exige ao
  menos 4 pacotes ARP.
- Fixtures de aceitação inalteradas (82,38 e 84,44); métricas internas 15/15, com
  abstenção de 0,267 para 0,200.
- Pesquisa refeita com o modelo novo (corpus v3): manual F1 0,6389 (antes 0,4950),
  GA 0,6490 e NSGA-II 0,6400; vantagem marginal (+0,010 e +0,001) com FPR maior.
  Resultados anteriores arquivados em `research/historical-invalid/v070-pre-adr0013/`.

## Não lançado — preparação de fechamento (28/09/2026)

- Render Free + Supabase Free escolhidos pelo grupo (ADR 0012); especificação
  render.yaml e CD condicionado aos três checks, à main e à ativação explícita.
- Cliente de deploy fixa SHA, aguarda live e verifica o commit. Smoke HTTPS
  confirma CSRF/sessão, REST e avanço da fonte sintética.
- Onze testes offline da entrega cloud; nenhum deploy real executado nesta etapa.
- Guias de execução por etapa, ficha de evidências, pitch e sabatina.
- Documentação atualizada com PRs/CI existentes e aprovação da trilha própria.
- Núcleo operacional e resultados/hiperparâmetros de otimização preservados.

## 0.7.0

- `SecurityIdentity` e `trusted_bindings()` separam o inventário confiável da autorização de mitigação.
- Detecção ampla com mitigação restrita: qualquer MAC com score >= 65 falsificando um IP confiável vira ameaça confirmada, mas só o MAC autorizado é mitigado; os demais emitem `threat_unmitigable` (ADR 0008).
- `arp_reply_ratio` entra nas cinco regras Mamdani, sem criar regra nova. O piso 0,5 está justificado em [docs/validation/fuzzy-metrics.md](docs/validation/fuzzy-metrics.md).
- Telemetria da captura no snapshot e no modal do dashboard.
- Corpus de evidência compartilhado entre Python e JavaScript, com `reason_code` (emenda da ADR 0006).
- Histórico de risco em `GET /api/devices/<mac>/history`, com sparkline no modal.
- CSP no header HTTP, contraste das bordas corrigido e motivo visível quando o calibrate fica desabilitado.
- Poda manual de eventos: `python -m netsentinel.api prune --keep-days DIAS [--confirm]`.

Medido nesta versão: 148 testes Python e 14 testes JavaScript.

## 0.6.0

- `Dockerfile` multi-stage (frontend, instalação Python, runtime) e `docker-compose.yml` com serviço sintético e Postgres local. Roteiro em [docs/docker.md](docs/docker.md).
- Duas avaliações consecutivas qualificando o mesmo MAC antes da mitigação; uma avaliação que não qualifica reinicia a sequência (ADR 0007).

Medido na época: 101 testes Python e 9 JavaScript.

## 0.5.0

- Dashboard: topologia vis.js, tabela de dispositivos e risco, reconhecimento manual, calibração, eventos, auditoria e evidências do agente.
- Backend e dashboard passam a reutilizar `SecurityDemo` e `VictimAgentMitigationStrategy`.
- JavaScript puro e Tailwind compilado, com todos os assets servidos localmente.

## 0.4.0

- Persistência com SQLAlchemy 2 e migrações Alembic.
- Promoção manual e auditada de reputação NEW para KNOWN (ADR 0004).
- Baseline congelado pela mediana de cinco taxas em bytes/s (ADR 0005).
- Sessão do operador com CSRF. Cookie `Secure=False` no laboratório HTTP e `Secure=True` na nuvem; `HttpOnly` e `SameSite=Lax` em ambos.
