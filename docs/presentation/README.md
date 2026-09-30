# Evidências de apresentação

Roteiro de pitch e perguntas para todos: [preparação](../closure/presentation.md).
Ficha para registrar execução: [evidence-template.md](../closure/evidence-template.md).

| Requisito | Evidência existente | Ainda falta |
|---|---|---|
| 1 — Open source | Repositório público, PRs [#3](https://github.com/dantas-eng/netsentinel/pull/3)/[#4](https://github.com/dantas-eng/netsentinel/pull/4), revisão por outro integrante e CI | Identificar a versão final demonstrada |
| 2 — Segurança | Código e testes offline | Ensaio real: ping, Host-only, ARP, nftables e deltas |
| 3 — Inteligência | [Relatório vigente](../../research/results/report.md), Pareto, 20 sementes/método e aprovação da trilha | Preparar explicação oral de modelo/protocolo/limitações |
| 5 — Cloud | [CI pública](https://github.com/dantas-eng/netsentinel/actions/runs/35897359835) com container/Postgres; CD preparado | URL HTTPS, execução real de CD, banco gerenciado e navegador |

Não publicar senha, token, `.env`, cookies ou hash de credencial. Não marcar
ensaio/deploy como aprovado apenas porque existe roteiro ou código para executá-lo.
