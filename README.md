# NetSentinel

NetSentinel observa o tráfego de uma rede local, calcula o risco de cada
dispositivo com lógica fuzzy e aciona a defesa contra ARP spoofing no host
atacado. Projeto integrador de Engenharia da Computação para a ExpoTech 2026.2.

## Como funciona

O sensor captura tráfego Ethernet e ARP com Scapy e publica um snapshot por
segundo. Cada snapshot passa pelo motor fuzzy Mamdani, que combina conflito de
IP, frequência de ARP, reputação, desvio de volume e razão de replies em um score
de 0 a 100. Acima de 65, com falsificação de um IP do inventário confiável, a
ameaça é confirmada. Para o atacante autorizado no laboratório, um agente na
máquina vítima aplica ARP estático e regra nftables, e o sistema só considera a
defesa efetiva depois de conferir os contadores antes e depois do filtro.

Camadas, padrões de projeto e ordem de execução estão em
[docs/architecture/overview.md](docs/architecture/overview.md).

## Requisitos

Python 3.11 ou superior, em Linux. As dependências estão em `pyproject.toml`.
Node é necessário só para editar e recompilar o frontend, não para usar o
sistema.

## Instalação

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Se as VMs forem isoladas depois, instale as dependências antes ou transfira os
wheels.

## Uso

### Captura no sensor

```bash
sudo .venv/bin/python -m netsentinel.capture \
  --interface INTERFACE_INTERNA_DO_SENSOR \
  --window-seconds SEGUNDOS \
  --max-observations LIMITE \
  --isolated-lab
```

A saída é JSON Lines, uma linha por snapshot. O contrato dos campos está em
[docs/capture.md](docs/capture.md), e a montagem do laboratório em
[lab/README.md](lab/README.md).

### Backend e dashboard

```bash
.venv/bin/python -m netsentinel.api serve
```

Abra `http://<IP-Host-only-do-Sensor>:<PORT>/` no navegador. O dashboard mostra
topologia, dispositivos e risco, eventos, auditoria e as evidências do agente.
Detalhes do contrato REST e Socket.IO em [docs/backend.md](docs/backend.md); o
escopo da interface em [docs/dashboard.md](docs/dashboard.md).

### Docker

O Compose sobe a aplicação com dados sintéticos e Postgres local. Roteiro em
[docs/docker.md](docs/docker.md).

## Testes

```bash
PYTHONPATH=src .venv/bin/python tests/run_offline.py
cd frontend && npm ci && npm test
```

São 148 testes Python e 14 JavaScript, em Python 3.12 com Scapy 2.7.0 e
scikit-fuzzy 0.5.0. O runner offline evita a descoberta de interfaces e rotas do
host, mas mantém o Scapy real para construir, dissecar e ler PCAP. O socket é
mockado nos testes de ciclo de vida e nenhum pacote é transmitido.

O CI roda lint e as duas suítes a cada pull request e a cada push em `main`.

## Documentação

- [Arquitetura e padrões](docs/architecture/overview.md)
- [Captura e contrato de saída](docs/capture.md)
- [Motor fuzzy](docs/fuzzy.md)
- [Backend](docs/backend.md) · [Dashboard](docs/dashboard.md) · [Docker](docs/docker.md)
- [Laboratório com as quatro VMs](lab/README.md)
- [Decisões de arquitetura](docs/decisions/)
- [Changelog](CHANGELOG.md)

## Estado do projeto

Captura, motor fuzzy, backend, dashboard, agente de mitigação e ambiente Docker
estão implementados e cobertos por testes offline. O ensaio completo nas quatro
VMs, com ping caindo e voltando e nftables no kernel, ainda não foi feito, e o
deploy em nuvem continua pendente. O mapa detalhado do que está comprovado e do
que falta está em [docs/compliance.md](docs/compliance.md).

## Licença

MIT, veja [LICENSE](LICENSE). Para contribuir, leia
[CONTRIBUTING.md](CONTRIBUTING.md).
