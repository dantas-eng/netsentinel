# Evidências de validação

Este diretório guarda artefatos que comprovam comportamento. Está vazio de
ensaios: nada aqui foi fabricado para parecer concluído.

Mapeamento dos blocos **Para fechar:** de [docs/compliance.md](../compliance.md):

| Requisito | O que depositar aqui | Ainda não existe |
| --- | --- | --- |
| 2 — Telecom e segurança | PCAP/log do Sensor com visibilidade unicast; registro do ataque sem forwarding; deltas de `seen`/`dropped`/`passed` do mesmo ensaio; confirmação de ARP estático | Ensaio nas quatro VMs |
| 3 — Inteligência computacional | Relatório gerado pelo harness (`fuzzy-metrics.md`), quando existir | Harness ainda não implementado |
| 5 — Cloud | Saída do Compose com Postgres real; revisão Alembic; URL e commit do deploy | Conta de nuvem e execução pública de CI |

Não colocar senha, token, `.env` ou hash de credencial.
