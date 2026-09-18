# Captura

Como rodar o sensor e o que ele emite. A montagem do laboratório está em
[lab/README.md](../lab/README.md).

## Executando

```bash
sudo .venv/bin/python -m netsentinel.capture \
  --interface INTERFACE_INTERNA_DO_SENSOR \
  --window-seconds SEGUNDOS \
  --max-observations LIMITE \
  --isolated-lab
```

Não há janela ou limite padrão: os três valores vêm da configuração do grupo.

`--isolated-lab` é uma declaração de configuração, não uma verificação. O processo
não consegue inspecionar o VirtualBox; o isolamento é responsabilidade da
infraestrutura. A captura acontece só na interface passada. `Ctrl+C` e `SIGTERM`
encerram a captura, publicam a última janela e fecham o socket.

## Saída

Cada linha é um snapshot JSON. O campo `source=live` identifica esta fonte; a
fonte sintética usada na nuvem se identifica separadamente.

| Campo | Conteúdo |
| --- | --- |
| `devices` | Por MAC de origem Ethernet: bytes, requests e replies ARP, primeiro e último timestamp dentro da janela. Não é reputação histórica. |
| `arp_claims` | IP anunciado, MAC declarado no ARP, MAC de origem Ethernet e contagem. Requests e replies ficam separados nas métricas por dispositivo. |
| `links` | Pares direcionados origem/destino Ethernet, incluindo broadcast e multicast. Não equivale à lista de dispositivos físicos descobertos. |
| `incomplete` | Houve descarte por capacidade que ainda afeta a janela atual. O motor fuzzy trata as entradas desse snapshot como ausentes. |
| `evicted_total` | Descartes acumulados pela capacidade da aplicação. Não mede perdas no kernel, no switch ou no adaptador. |
| `unsupported_total`, `malformed_total` | Observações que não foram aproveitadas. |

Probes com IP de origem `0.0.0.0` não contam como afirmação de propriedade de
endereço.

## Janela

A janela é móvel, medida pelo instante monotônico de ingestão, no intervalo
`(agora - duração, agora]`. O timestamp do pacote é preservado para a timeline.
Um snapshot sai aproximadamente a cada segundo, inclusive quando a rede está em
silêncio.

`observed_seconds` informa o tempo efetivamente observado, limitado à duração da
janela. `warming_up` indica que a primeira janela ainda não fechou — não se deduz
baseline nem reputação a partir do primeiro pacote.

O volume conta bytes capturados por origem. Não há payload persistido, contagem
de overhead físico nem deduplicação implícita.

## Socket

O socket fica aberto entre publicações, em modo promíscuo e com `store=False`. O
consumidor é síncrono e precisa ser rápido. Os snapshots agregados são
recalculados em O(n), e o módulo ainda não foi validado como coletor de alto
volume.

API do Scapy usada aqui:
<https://scapy.readthedocs.io/en/latest/api/scapy.sendrecv.html>
