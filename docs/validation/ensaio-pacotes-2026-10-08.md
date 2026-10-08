# Ensaio em namespaces — quadros ARP no visualizador (08/10/2026)

- Commit: `a9b2c73` (branch `feat/visualizador-pacotes`).
- Ambiente: quatro namespaces Linux (Gateway, Vítima, Atacante, Sensor) numa
  bridge com `ageing_time 0`, como hub; Host-only 192.168.56.0/24 até o Sensor.
  Kernel do sandbox sem IPv6: um shim responde `0` aos sysctl IPv6 ausentes.
  Não é o ensaio das VMs VirtualBox e não o substitui.
- Responsável: Matheus Dantas.

## Roteiro

1. Backend em modo lab no Sensor (`python -m netsentinel.api migrate`,
   `bootstrap`, `serve`) com o agente na Vítima e `tcpdump -w` do ARP no Sensor.
2. Ping Vítima → Gateway; após 18 s, `netsentinel.security.attack --pps 10
   --seconds 25` no Atacante.
3. Pelo Host-only: login, `GET /api/packets?latest=1&spoofed=1`,
   `GET /api/packets/{id}` e `GET /api/packets/match`; comparação de `raw_hex`
   com os quadros do pcap.

## Resultado

| Verificação | Observado |
|---|---|
| Quadros guardados em ~90 s | 217 (207 anúncios do Atacante e 10 legítimos); cerca de 20 linhas por janela de 8 s |
| Alegações falsas listadas | 207, todas `02:00:00:00:00:30` alegando `10.77.0.1` |
| Veredito do quadro aberto | `spoofed_trusted_ip`, esperado `02:00:00:00:00:10` |
| Camadas | Ethernet II e ARP reply; MAC do remetente em [22:28], IP do remetente em [28:32] |
| Bytes da API × `tcpdump -XX` | idênticos para todos os 207 quadros falsos (42 bytes; veth não preenche até 60) |
| "Ver pacote" (`match`) da primeira detecção | quadro 7, `captured_at` anterior ao evento |
| `match` antes do ataque | 404 `packet_not_retained` |
| Erros no servidor | nenhum traceback; uma `mitigation_applied` registrada |

Trecho do `tcpdump -nn -XX` no Sensor:

```text
ARP, Reply 10.77.0.1 is-at 02:00:00:00:00:30, length 28
	0x0000:  0200 0000 0020 0200 0000 0030 0806 0001  ...........0....
	0x0010:  0800 0604 0002 0200 0000 0030 0a4d 0001  ...........0.M..
	0x0020:  0200 0000 0020 0a4d 0014                 .......M..
```

## Limites

- Namespaces não comprovam visibilidade unicast no VirtualBox (Allow All) nem o
  volume real do laboratório; repetir a conferência `tcpdump -XX` nas VMs.
- O modal foi conferido em Chromium headless com a fonte sintética; no ensaio só a
  API foi exercitada.
