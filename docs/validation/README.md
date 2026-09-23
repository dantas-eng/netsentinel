# Evidências de validação

Este diretório guarda artefatos que comprovam comportamento. Está vazio de
ensaios: nada aqui foi fabricado para parecer concluído.

Mapeamento dos blocos **Para fechar:** de [docs/compliance.md](../compliance.md):

| Requisito                      | O que depositar aqui                                                                                                                                             | Status                                                                                                                                                                                      |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2 — Telecom e segurança        | PCAP/log do Sensor com visibilidade unicast; registro do ataque sem forwarding; deltas de `seen`/`dropped`/`passed` do mesmo ensaio; confirmação de ARP estático | Ainda não existe — falta o ensaio nas quatro VMs                                                                                                                                            |
| 3 — Inteligência computacional | Relatório gerado pelo harness                                                                                                                                    | Já existe: [fuzzy-metrics.md](fuzzy-metrics.md), gerado por `tools/fuzzy_metrics.py`                                                                                                        |
| 5 — Cloud                      | Saída do Compose com Postgres real; revisão Alembic; URL e commit do deploy                                                                                      | Parcial — o job `container` do CI já builda a imagem, sobe o Compose com Postgres real e confere a revisão Alembic (ver PR #1); ainda falta conta de nuvem e deploy público (ex: Cloud Run) |

Não colocar senha, token, `.env` ou hash de credencial.
