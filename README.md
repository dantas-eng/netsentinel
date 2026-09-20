# NetSentinel

[![versão](https://img.shields.io/badge/versão-0.7.0-informational)](CHANGELOG.md)
[![licença](https://img.shields.io/badge/licença-MIT-blue.svg)](LICENSE)

Observa uma rede local isolada, pontua o risco de cada dispositivo e aplica
defesa contra ARP spoofing no host atacado. Projeto integrador de Engenharia da
Computação, ExpoTech 2026.2, categoria NEXUS.

## O problema

Numa LAN, o ARP associa IP a MAC sem autenticação. Um atacante pode anunciar o
IP do gateway com o próprio MAC; o tráfego da vítima passa a ir para ele. Este
projeto trata desse recorte num laboratório de quatro VMs, sem uplink e sem uso
em rede de terceiros.

## O que o sistema faz

1. O sensor observa Ethernet e ARP e fecha uma janela de tráfego a cada segundo.
2. O motor fuzzy Mamdani combina conflito de IP, frequência de ARP, reputação,
   desvio de volume e razão de replies num score de 0 a 100. A partir de 65 o
   dispositivo é classificado como suspeito.
3. A ameaça só se confirma com score alto **e** falsificação de um IP do
   inventário confiável (gateway, vítima, sensor ou atacante).
4. Só o MAC autorizado no laboratório é mitigado: ARP estático e regra nftables
   na máquina vítima. Qualquer outro MAC confirmado gera o evento
   `threat_unmitigable`.
5. A defesa só conta depois da conferência dos contadores antes e depois do
   filtro. Silêncio ou volta de ping, sozinhos, não bastam.

## Como ler este repositório

A tabela abaixo relaciona tópicos do projeto aos arquivos onde estão documentados.

| Pergunta | Onde está |
| --- | --- |
| Camadas, padrões e ordem de execução | [docs/architecture/overview.md](docs/architecture/overview.md) |
| Regras fuzzy, limiares e fixtures | [docs/fuzzy.md](docs/fuzzy.md) |
| Contrato da captura e da janela | [docs/capture.md](docs/capture.md) |
| Laboratório das quatro VMs | [lab/README.md](lab/README.md) |
| O que já está comprovado e o que falta | [docs/compliance.md](docs/compliance.md) |
| Decisões (ARP sem forwarding, reputação, evidência) | [docs/decisions/](docs/decisions/) |
| Backend, dashboard e Docker | [docs/backend.md](docs/backend.md) · [docs/dashboard.md](docs/dashboard.md) · [docs/docker.md](docs/docker.md) |
| Histórico de versões | [CHANGELOG.md](CHANGELOG.md) |

## Recorte desta entrega

Já implementados e cobertos por teste offline: captura, motor fuzzy, backend,
dashboard, agente de mitigação, ambiente Docker e configuração de CI ainda não publicada. O ensaio completo
nas quatro VMs (ping caindo e voltando, nftables no kernel) e o deploy em nuvem
ainda não foram feitos. O mapa de evidências está em
[docs/compliance.md](docs/compliance.md).

## Reproduzir

Python 3.11 ou superior, em Linux.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
PYTHONPATH=src .venv/bin/python tests/run_offline.py
```

Resultado esperado: `Ran 148 tests` e `OK`. No frontend, `cd frontend && npm ci && npm test` deve encerrar com `# pass 14`. O Compose com dados sintéticos está em [docs/docker.md](docs/docker.md). A captura no sensor e a montagem das VMs estão em [lab/README.md](lab/README.md).

## Licença

MIT. Ver [LICENSE](LICENSE). Fluxo de contribuição em
[CONTRIBUTING.md](CONTRIBUTING.md).

## Integração local 0.7.0 + otimização

Entrega consolidada por arquivos, sem histórico Git ou repositório remoto existente.
A versão operacional permanece 0.7.0; nenhuma tag Git é afirmada. Publicação e
primeiro commit serão realizados pelo grupo. O módulo opcional `optimization/`
usa o baseline manual desta versão e quatro genes; veja
[ADR 0010](docs/decisions/0010-integracao-070-otimizacao.md),
[reprodução](research/README.md) e [validação](research/VALIDATION.md).

A comparação experimental vigente usa corpus ARP v2 com requests/replies variados.
As duas tentativas anteriores são inválidas para comparação atual e ficam em
`research/historical-invalid/`. Consulte a
[ADR 0011](docs/decisions/0011-corpus-arp-variavel-e-validade-experimental.md).
