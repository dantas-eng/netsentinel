# Visualizador de pacotes ARP — design

Data: 08/10/2026. Base: main 8ec1f74.

## Objetivo

Permitir que o operador, e a banca na demonstração, abra um pacote ARP observado
pelo Sensor e veja a dissecação camada por camada, como no Wireshark: árvore de
campos, bytes em hexadecimal com destaque cruzado e um veredito dizendo se o
quadro alega um vínculo IP→MAC diferente do inventário confiável. O caso central é
abrir a resposta ARP falsa do Atacante e ver os dois campos que mentem.

Funciona no laboratório (captura real) e na nuvem (fonte sintética).

## Decisões (aprovadas pelo grupo)

- **D1. Só ARP, quadro inteiro.** Guardar apenas quadros ARP Ethernet/IPv4, com os
  bytes completos até 128 bytes. ARP não carrega dado de usuário. Outros quadros
  continuam descartados depois da extração de metadados, como hoje.
- **D2. Guardar no banco.** Tabela nova `arp_frames` via Alembic, a mesma em SQLite
  (laboratório) e Postgres/Supabase (nuvem). O laboratório nunca grava no Supabase:
  a rede das VMs é isolada; no Supabase ficam só os quadros sintéticos da nuvem.
- **D3. Retenção dupla.** Apagar quadros com mais de `PACKET_RETENTION_DAYS` dias
  (padrão 5) e manter no máximo `PACKET_MAX_ROWS` (padrão 20000), removendo os
  mais antigos primeiro. A poda roda na mesma transação da gravação em lote de cada
  janela; o comando `python -m netsentinel.api prune` também poda quadros.
- **D4. Dissecação no backend.** Um módulo Python transforma bytes em camadas e
  campos com intervalo de bytes; o frontend só desenha. O veredito usa
  `trusted_bindings()`, o mesmo inventário do detector.
- **D5. Modal.** Clicar num pacote da lista abre um `<dialog>` com veredito,
  detalhes e bytes lado a lado, navegação Anterior/Próximo e Esc para fechar.

## Captura e fonte sintética

- `CaptureService.ingest`: quando o quadro normalizado é ARP Ethernet/IPv4 válido
  (`hwtype=1, ptype=0x0800, hlen=6, plen=4`), acumula
  `{timestamp, raw: bytes(packet[Ether])[:128]}` numa lista pendente. `emit()`
  inclui a lista no snapshot como `arp_frames` e zera a lista.
- `SyntheticSource.snapshot()` gera quadros reais em bytes para a mesma janela:
  pedido da Vítima pelo gateway e resposta do gateway (legítimos), e, depois de
  `ATTACK_AFTER_SECONDS` e `INTRUDER_AFTER_SECONDS`, respostas falsas do Atacante
  (alegando o IP do gateway) e do intruso (alegando o IP da Vítima). Quantidade
  proporcional ao que a fonte já declara em `arp_replies`, limitada a 10 quadros
  por snapshot para não inflar o banco.
- `BackendPipeline.consume`: retira `arp_frames` do snapshot antes de
  `save_snapshot` e grava via `repository.save_arp_frames(frames, capture_run_id,
  source)`. Os bytes nunca entram no JSON do snapshot.

## Banco

Tabela `arp_frames`:

| Coluna | Tipo | Nota |
|---|---|---|
| `id` | inteiro, PK autoincremento | ordem de chegada |
| `captured_at` | float (epoch) | indexado |
| `capture_run_id` | texto | |
| `source` | texto | `live` ou `synthetic` |
| `eth_src`, `eth_dst` | texto (MAC minúsculo) | `eth_src` indexado |
| `opcode` | inteiro | 1 request, 2 reply |
| `sender_mac`, `sender_ip`, `target_mac`, `target_ip` | texto | `sender_ip` indexado |
| `raw` | binário (até 128 bytes) | |

Os campos decodificados em colunas existem para filtro e busca; a fonte da verdade
exibida no modal é o `raw` dissecado.

Repositório:

- `save_arp_frames(frames, capture_run_id, source, now)`: decodifica cada quadro com
  o dissecador, insere em lote e poda por idade e por limite na mesma transação.
- `arp_frames(after_id, limit, spoofed_only, query, trusted)`: lista paginada
  crescente por `id`, `1 <= limit <= 500`. `query` busca em MACs, IPs; `spoofed_only`
  filtra pelo inventário recebido.
- `arp_frame(id)`: um quadro com `raw`.
- `match_arp_frame(mac, ip, before)`: o quadro mais recente com `eth_src = mac`,
  `sender_ip = ip` e `captured_at <= before`, ou `None`.
- `prune_arp_frames(retention_days, max_rows, now)`: usado pela gravação e pelo
  comando de poda.

## Dissecação

`src/netsentinel/packets/dissect.py`:

- `dissect(raw: bytes) -> dict` retorna `{layers: [{name, fields: [{name, value,
  start, end}]}], summary, opcode, sender_mac, sender_ip, target_mac, target_ip,
  length}`. Camadas: `Ethernet II`, `802.1Q` quando houver tag VLAN,
  `Address Resolution Protocol (request|reply)`, `Preenchimento` quando houver
  bytes após o ARP.
- Quadro curto, EtherType diferente de ARP ou ARP de formato não Ethernet/IPv4
  levanta `ValueError` com mensagem clara; o pipeline descarta o quadro e conta em
  `malformed_total`, sem interromper a captura.
- `verdict(dissected, trusted) -> dict`: `{spoofed: bool, expected_mac | None,
  reason}`. Só respostas e pedidos com `sender_ip` presente no inventário e
  `sender_mac` diferente do esperado são falsos. `0.0.0.0` (probe) nunca é falso.

## API

Todas autenticadas, `Cache-Control: no-store`, mesmos cabeçalhos das demais.

- `GET /api/packets?after_id=0&limit=100&spoofed=0|1&q=` →
  `{packets: [{id, captured_at, eth_src, eth_dst, opcode, sender_mac, sender_ip,
  target_mac, target_ip, length, summary, spoofed}]}`.
- `GET /api/packets/<id>` → item da lista mais `{raw_hex, layers, verdict}`;
  404 se não existir.
- `GET /api/packets/match?mac=&ip=&before=` → mesmo formato de `/<id>` ou
  `404 {error: "packet_not_retained"}`.
- Validação: `mac` no formato `xx:xx:xx:xx:xx:xx`, `ip` IPv4, `before` número finito,
  `q` até 64 caracteres; parâmetros sempre passados ao SQLAlchemy como valores.

Tempo real: sem evento Socket.IO novo. A reconciliação REST disparada por
`snapshot_updated` inclui `GET /api/packets?after_id=<último>`.

## Frontend

No dashboard atual (`dashboard.html`, `dashboard.mjs`, `core.mjs`, `styles.css`):

- Seção "Pacotes ARP" abaixo da topologia: lista com rolagem própria (máximo de 500
  linhas na tela, mais novas primeiro), filtro de texto, opção "só alegações
  falsas", contador e navegação por teclado (setas, Enter). Linha falsa com faixa
  lateral e texto em vermelho.
- Modal `<dialog>`: título "Pacote N, ARP request|reply", hora, tamanho e origem →
  destino; veredito; painel de detalhes com a árvore; painel de bytes com offset,
  hex e ASCII; destaque cruzado campo↔byte; bytes dos campos falsos em vermelho;
  Anterior/Próximo (e setas ←/→) pela lista filtrada; Esc e Fechar devolvem o foco à
  linha.
- "Ver pacote" nos eventos `risk_evaluated` com ameaça e `threat_unmitigable` do
  histórico, e no modal do dispositivo quando ele é origem de alegação falsa. Usa
  `/api/packets/match`. Se 404: "O quadro desta detecção não está mais guardado
  (retenção de 5 dias)."
- Todo conteúdo por `textContent`. Funções puras em `core.mjs`:
  `hexRows(rawHex)` e `byteOwners(layers, length)`.

## Testes

- Dissecador: request, reply, quadro com VLAN, preenchimento, quadro truncado,
  EtherType errado, ARP não Ethernet/IPv4, quadro maior que 128 bytes cortado.
- Veredito: falso, legítimo, IP fora do inventário, probe `0.0.0.0`.
- Captura: ARP válido vai para `arp_frames`; IPv4 e ARP de outro formato não vão;
  lista zera a cada `emit()`.
- Fonte sintética: quadros legítimos sempre; falsos do Atacante após 60 s e do
  intruso após 90 s; no máximo 10 por snapshot.
- Pipeline: `arp_frames` não aparece no snapshot persistido.
- Repositório (SQLite na suíte offline e Postgres no job de container): gravação em
  lote, poda por idade, poda por limite, paginação, filtros, `match` antes e depois
  do instante.
- API: 401 sem sessão, `no-store`, 400 para parâmetros inválidos, 404 e
  `packet_not_retained`, veredito igual ao de `trusted_bindings()`.
- Frontend (node:test): `hexRows` e `byteOwners`, incluindo intervalos que cruzam a
  linha de 16 bytes.
- Ensaio em namespaces: abrir a resposta falsa do Atacante no modal e conferir os
  bytes com `tcpdump -XX` no Sensor.

## Documentação

ADR 0014 (quadros ARP, retenção e dissecação no backend); `docs/capture.md`,
`docs/backend.md`, `docs/dashboard.md`, `docs/compliance.md` (evidência do
requisito de redes), pergunta nova em `docs/closure/presentation.md`, `CHANGELOG.md`,
`.env.example` e `render.yaml` com as duas variáveis novas.

## Riscos

- Volume na nuvem: limite de linhas protege o plano gratuito do Supabase.
- Gravação por janela no SQLite do laboratório: cerca de 80 linhas a cada 8 s no pior
  caso do ensaio; medir no ensaio em namespaces.
- Conflito com o PR #6 em `dashboard.html`, `dashboard.mjs` e `styles.css`: este
  trabalho parte da main; se o #6 entrar antes, rebase.
- Numeração de ADR: o PR #7 cria a 0013; esta mudança usa a 0014 para não colidir.

## Fora do escopo

Quadros que não são ARP, payload de qualquer protocolo, exportação PCAP, filtros com
sintaxe do Wireshark, eventos Socket.IO novos.
