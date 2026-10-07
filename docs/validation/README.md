# Evidências de validação

| Requisito | Evidência | Alcance/pendência |
|---|---|---|
| Segurança | [Roteiro VMs](../closure/lab-validation.md) e [ficha](../closure/evidence-template.md) | Ensaio real ainda pendente; não fabricar PCAP/contadores de aceitação |
| Inteligência | [fuzzy-metrics.md](fuzzy-metrics.md) e [research/results/report.md](../../research/results/report.md) | Resultados sintéticos; não são validação em rede real |
| Classificação de legítimos | [ensaio-namespaces-2026-10-07.md](ensaio-namespaces-2026-10-07.md) | Namespaces com kernel/nftables reais; antecipa, não substitui, as 4 VMs |
| Cloud | [CI main](https://github.com/dantas-eng/netsentinel/actions/runs/35897359835) | Container/Postgres real comprovados; Render/Supabase/CD e browser ainda pendentes |
| Preparação de fechamento | [closure-preparation.md](closure-preparation.md) | Testes locais de scripts/configuração; não é deploy |

Depositar aqui ou referenciar artefatos sanitizados dos ensaios, com data,
responsável, commit e ambiente. Não anexar senha, token, cookie ou URL de banco.
