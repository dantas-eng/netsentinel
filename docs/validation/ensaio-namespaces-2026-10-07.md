# Ensaio em namespaces com a classificação nova (07/10/2026)

Registro do ensaio que valida, com kernel, Scapy e nftables reais, a
classificação de dispositivos legítimos da
[ADR 0013](../decisions/0013-classificacao-de-dispositivos-legitimos.md).
**Antecipa, mas não substitui, o ensaio nas quatro VMs exigido pelo roteiro**
([lab-validation](../closure/lab-validation.md)); o ensaio nas VMs segue pendente.

## Método

- Commit testado: `9c1391c` (branch `feat/classificacao-legitimos`).
- Ambiente: kernel Linux 6.18.44, Scapy 2.8.0, nftables 1.0.9, executado como root.
- Quatro network namespaces (gateway `10.77.0.1`, Vítima `.20`, Atacante `.30`,
  Sensor `.40`) ligados a uma bridge Linux com `ageing_time 0`, que replica todos
  os quadros para todas as portas (modo hub), equivalente à rede interna do
  VirtualBox com "Allow All". O Sensor tem ainda uma interface host-only isolada.
- Agente real na Vítima (`agent serve`), Sensor real (`demo monitor`, captura
  Scapy), `tcpdump` de ARP no Sensor, `ping -i 0.5` da Vítima ao gateway e
  log da tabela de vizinhos da Vítima a cada segundo.
- Cenário: ~20 s de observação sem ataque; ataque de 40 s a 10 pps
  (334 anúncios ARP falsos do Atacante alegando ser o gateway); `demo verify`
  (evidência de 5 s) executado **durante** o ataque, 15 s após o início.
- Os scripts (criação dos namespaces, execução e análise) ficaram fora do
  repositório; não são evidência versionada.
- Desvio do sandbox: o kernel do ambiente não tem sysctls de IPv6; o ensaio roda
  com um shim que faz um sysctl `ipv6` ausente ler como `0`. Nenhuma outra
  alteração de código ou parâmetro foi feita.

## Resultado

Tempos em segundos a partir do início do ataque (t=0); o ataque termina em t=41.
Cada linha é uma avaliação por segundo do Sensor (score fuzzy 0-100).

| Dispositivo | Antes (t<0) | Durante (0 a 41 s) | Depois (>41 s) |
|---|---|---|---|
| Gateway `.10` | 15,6-16,6, confiável | 15,6-16,6, confiável | 15,6, confiável |
| Vítima `.20` | 15,6-16,6, confiável | 15,6-16,6, confiável | 15,6, confiável |
| Sensor `.40` | sem tráfego ARP; não aparece | 15,6-16,6, confiável (aparece em t=3,9) | 15,6, confiável |
| Atacante `.30` | não aparece | 82,4-84,4, suspeito (aparece em t=1,8) | 84,4, suspeito (até a última avaliação, ~t=49) |

Nos primeiros ~7 s de captura (aquecimento) todos aparecem sem avaliação
(`capture_warming_up`); depois disso nenhum legítimo ficou sem score ou
classificado como suspeito/desconhecido em nenhuma avaliação. O Sensor só entra
na lista quando passa a falar na rede (consulta ao agente após a detecção), por
isso não há "antes" para ele neste cenário.

### Critério da spec

| Critério | Resultado |
|---|---|
| Gateway, Vítima e Sensor `confiável` antes e durante o ataque | Atendido para gateway e Vítima. Sensor `confiável` em 100% das avaliações em que aparece (durante e depois); antes do ataque ele não emite ARP e não é avaliado. |
| Atacante `suspeito` | Atendido (82,4-84,4) |
| `mitigation_applied` | Atendido em t=2,8 s |
| Ping volta | Atendido (ver abaixo) |
| `verify` com `verified: true` | Atendido, durante o ataque |

### Ping Vítima -> gateway

139 requisições, 136 respostas. Perda de 3 pacotes consecutivos (`icmp_seq`
41-43), cerca de 2 s entre t=1,1 e t=3,1, que é a janela entre o primeiro
anúncio falso e a aplicação do ARP estático. Sem perdas depois disso, até o fim
do ataque e após ele.

### ARP do gateway na Vítima

| t | Entrada |
|---|---|
| antes de 0 | `02:00:00:00:00:10` REACHABLE (MAC legítimo) |
| 1 s | `02:00:00:00:00:30` REACHABLE (envenenada pelo Atacante) |
| 3 s | `02:00:00:00:00:10` PERMANENT (ARP estático aplicado) |

A entrada permaneceu PERMANENT com o MAC correto até o fim.

### Contadores nftables e `verify`

- `mitigation_applied` (t=2,8 s): visto 15 pacotes (420 B), descartados 0,
  passados 15, ou seja, os quadros do Atacante anteriores ao filtro.
- `verify` (início t=15, fim t=21): **`verified: true`**, escopo
  `post_filter_attacker_mac`, `reason` nulo.

| Contador | Antes | Depois | Delta |
|---|---|---|---|
| seen | 128 | 170 | 42 |
| dropped | 113 | 155 | 42 |
| passed | 15 | 15 | 0 |

Ambos os snapshots: `blocked: true`, `mitigated: true`, `arp_static_correct:
true`, vizinho PERMANENT com o MAC do gateway. O campo `ping_verified` do
`verify` é sempre `false` (o ping é evidência independente, acima).

### Observações

- Dois eventos `mitigation_error` (`retry_on_next_snapshot`) aparecem só em
  t≈52 s, no desligamento do ensaio (processos encerrados), sem relação com o
  ataque.
- O Atacante some do painel ~8 s depois do fim do ataque (envelhecimento da
  janela de observação) e `false_gateway_claim` volta a `false`.

## Limitação

Rede simulada no mesmo kernel, MACs e IPs fixos, sem VirtualBox, sem NIC
física e sem o Sensor com duas interfaces reais. Não substitui o ensaio nas
quatro VMs nem sua ficha de evidência; PCAP e contadores de aceite do roteiro
continuam pendentes.
