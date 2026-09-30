# Preparação de fechamento — 28/09/2026

Base: main 692a41482daaa42be081d73d9735e038e6d438be, confirmada no remoto.
Alterações locais preparadas para revisão; nenhum push/PR/deploy foi executado.

## Verificações desta entrega

| Verificação | Resultado |
|---|---|
| tests/run_offline.py | 159 aprovados: 148 anteriores + 11 de entrega cloud |
| research.tests.test_optimization | 18 aprovados, incluindo métricas armazenadas |
| Frontend npm test | 14 aprovados |
| Ruff | Sem apontamentos |
| npm ci e npm run build | Sucesso; assets sem diff |
| Actionlint 1.7.12 | Workflow sem apontamentos; shellcheck externo não executado |
| YAML local | plano Free, uma instância, Auto-Deploy Off, sem LAB_CONFIG/banco Render |
| Preservação | src/ e research/results/ sem alterações em relação à base |

Os 11 testes novos cobrem SHA publicado, espera até live, commit divergente,
falhas/timeout, entrada inválida, CSRF-first, logout, origem sintética e fonte
avançando. A API do provedor e HTTP são substituídos por doubles nesses testes.
Não são prova de deploy, política de cookies no navegador ou disponibilidade real.

Não foram executados nesta etapa: Render/Supabase, Docker/Compose local (daemon
não disponível), navegador ou VirtualBox/nftables. A execução anterior da
[CI pública](https://github.com/dantas-eng/netsentinel/actions/runs/35897359835)
comprova container/Postgres na base; a nova revisão ainda precisa passar pela CI
no PR real. Não foram refeitas as 40 buscas evolutivas nem alterados seus resultados.

## Entrega e revisão

Ver docs/closure/README.md para aplicar o patch, revisar e integrar. O CD não
executa sem RENDER_DEPLOY_ENABLED=true, secrets e serviço configurados. As contas
permanecem sob controle do grupo; requisitos de nuvem/VMs continuam pendentes até
anexar evidência real à ficha de aceitação.
