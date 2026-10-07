# NetSentinel

[![CI](https://github.com/dantas-eng/netsentinel/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/dantas-eng/netsentinel/actions/workflows/ci.yml)
[![versão](https://img.shields.io/badge/versão-0.7.0-informational)](CHANGELOG.md)
[![licença](https://img.shields.io/badge/licença-MIT-blue.svg)](LICENSE)

NetSentinel detecta e mitiga ARP spoofing numa rede local isolada. Um sensor
passivo observa o tráfego, um classificador fuzzy pontua o risco de cada
dispositivo e, quando a ameaça se confirma, um agente na máquina atacada aplica
ARP estático e uma regra nftables. A defesa só é dada como comprovada depois que
os contadores do filtro mostram o tráfego do atacante sendo descartado.

Projeto integrador de Engenharia da Computação, ExpoTech 2026.2, categoria NEXUS.

> **Uso restrito a laboratório.** O código de ataque existe apenas para o ensaio
> nas quatro VMs isoladas, sem rota de saída. Não execute em redes de terceiros.

## O problema

O ARP associa endereços IP a endereços MAC sem nenhuma autenticação. Qualquer
máquina da LAN pode anunciar "o IP do gateway está no meu MAC", e as vítimas
passam a enviar o tráfego para ela. O NetSentinel trata esse caso: identifica
quem está alegando um IP que não é seu e protege a vítima sem depender de
reconfigurar o switch.

## Como funciona

1. **Captura.** O sensor escuta a interface interna em modo promíscuo e agrega
   quadros Ethernet e ARP numa janela móvel de 8 segundos, separando a origem
   Ethernet observada do MAC que o ARP alega.
2. **Classificação.** Um motor fuzzy Mamdani combina conflito de IP, frequência
   de ARP, reputação, desvio de volume e razão de respostas ARP num score de 0 a
   100. A partir de 65 o dispositivo é considerado suspeito.
3. **Confirmação.** A ameaça só é confirmada com score alto e alegação falsa sobre
   um IP do inventário confiável, em duas avaliações seguidas.
4. **Mitigação.** Somente o MAC autorizado no laboratório é mitigado. O agente da
   vítima aplica ARP estático para o gateway e bloqueia o MAC no ingresso com
   nftables. Outros MACs confirmados geram o evento `threat_unmitigable`.
5. **Evidência.** A defesa vale quando os contadores antes e depois do filtro
   mostram pacotes vistos e descartados, sem entrega após o filtro. Ping voltando,
   sozinho, não comprova nada.

O dashboard web mostra topologia, inventário, evidências de mitigação e o
histórico de eventos em tempo real. Em nuvem, o mesmo backend roda com dados
sintéticos e nunca se conecta ao laboratório.

## Laboratório

```
                 rede interna isolada (sem uplink)
   ┌──────────┬───────────────┬───────────────┬──────────┐
   │ Gateway  │ Vítima        │ Atacante      │ Sensor   │
   │          │ agente +      │ envenenamento │ captura, │
   │          │ nftables      │ ARP limitado  │ backend  │
   └──────────┴───────────────┴───────────────┴────┬─────┘
                                                    │ host-only
                                              notebook (dashboard)
```

Montagem das VMs, configuração e roteiro do ensaio em [lab/README.md](lab/README.md).

## Estado do projeto

| Parte | Situação |
| --- | --- |
| Captura, motor fuzzy, backend, dashboard e agente de mitigação | Implementados e cobertos por testes offline |
| Otimização dos parâmetros fuzzy com GA e NSGA-II | Implementada, com experimento reprodutível em [research/](research/README.md) |
| CI em cada pull request (lint, testes, frontend, container com Postgres) | Ativa e obrigatória para merge na `main` |
| Ensaio completo nas quatro VMs | Pendente |
| Deploy em nuvem (Render + Supabase) | Configurado, ainda não publicado |

O mapa de evidências, com o que cada arquivo ou teste comprova e o que ainda falta,
está em [docs/compliance.md](docs/compliance.md).

## Começando

Requisitos: Linux, Python 3.11 ou superior. Node 22 só é necessário para
recompilar o frontend; os assets compilados já estão versionados.

```bash
git clone https://github.com/dantas-eng/netsentinel.git
cd netsentinel
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Testes e lint, os mesmos que o CI executa:

```bash
.venv/bin/python -m ruff check .
PYTHONPATH=src .venv/bin/python tests/run_offline.py

# suíte de otimização (dependências opcionais)
.venv/bin/python -m pip install -r requirements-optimization.txt
.venv/bin/python -m unittest research.tests.test_optimization

# frontend
cd frontend && npm ci && npm test && npm run build
```

Nenhum teste usa sudo, VMs, token do agente ou nftables reais. Para explorar o
dashboard com dados sintéticos, siga [docs/docker.md](docs/docker.md). Para operar
o backend no laboratório, veja [docs/backend.md](docs/backend.md).

## Estrutura do repositório

| Caminho | Conteúdo |
| --- | --- |
| `src/netsentinel/capture/` | Captura Scapy, normalização e janela móvel |
| `src/netsentinel/analysis/` | Extração de features e motor fuzzy |
| `src/netsentinel/security/` | Detecção, ataque limitado, agente da vítima e verificação de evidência |
| `src/netsentinel/api/` | Backend Flask, Socket.IO e dashboard |
| `src/netsentinel/optimization/` | Otimização offline com GA e NSGA-II |
| `frontend/` | Fonte Tailwind, build dos assets e testes JavaScript |
| `tests/` | Suíte offline e fixtures PCAP |
| `research/` | Corpus, resultados e validação da otimização |
| `lab/` | Configurações de exemplo das VMs |
| `docs/` | Arquitetura, contratos, decisões (ADRs) e guias de fechamento |

## Documentação

| Assunto | Documento |
| --- | --- |
| Camadas, padrões de projeto e ordem de execução | [docs/architecture/overview.md](docs/architecture/overview.md) |
| Regras fuzzy, limiares e fixtures | [docs/fuzzy.md](docs/fuzzy.md) |
| Contrato da captura e da janela | [docs/capture.md](docs/capture.md) |
| API, sessão e eventos | [docs/backend.md](docs/backend.md) |
| Dashboard | [docs/dashboard.md](docs/dashboard.md) |
| Decisões registradas | [docs/decisions/](docs/decisions/) |
| Guia de fechamento da entrega | [docs/closure/README.md](docs/closure/README.md) |
| Histórico de versões | [CHANGELOG.md](CHANGELOG.md) |

## Contribuindo

Todo trabalho entra na `main` por pull request, com os três checks do CI verdes e
aprovação de outro integrante. O fluxo completo está em
[CONTRIBUTING.md](CONTRIBUTING.md).

## Licença

Distribuído sob a licença MIT. Veja [LICENSE](LICENSE). As licenças dos
componentes de terceiros usados no dashboard ficam em
`src/netsentinel/api/static/vendor/licenses/`.
