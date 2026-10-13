# ADR 0014 — Quadros ARP guardados e visualizador no dashboard

- Data: 08/10/2026.
- Status: aprovada pelo grupo; implementada na branch `feat/visualizador-pacotes`.
- Design: [docs/specs/2026-10-08-visualizador-pacotes-design.md](../specs/2026-10-08-visualizador-pacotes-design.md).

## Contexto

O dashboard mostrava o score e o evento de ameaça, mas não o pacote que levou a
eles. Na sabatina, a pergunta "como vocês sabem que aquele quadro é falso?" só tinha
resposta no terminal (`tcpdump`). O grupo quer abrir o quadro no próprio dashboard,
com camadas e bytes como no Wireshark, e mostrar quais campos contradizem o
inventário. A captura descartava os bytes depois de extrair os metadados.

## Decisão

1. **Só ARP, quadro inteiro.** Guardar apenas quadros ARP Ethernet/IPv4, até 128
   bytes. ARP não carrega dado de usuário; os demais quadros continuam descartados
   depois da extração de metadados.
2. **No banco, pelo Alembic.** Tabela `arp_frames` (migração `0002_arp_frames`), a
   mesma em SQLite no laboratório e Postgres/Supabase na nuvem. O laboratório nunca
   grava no Supabase: lá só existem os quadros sintéticos da nuvem.
3. **Retenção dupla.** Apagar quadros com mais de `PACKET_RETENTION_DAYS` dias
   (padrão 5) e manter no máximo `PACKET_MAX_ROWS` (padrão 20000), mais antigos
   primeiro. A poda roda na mesma transação de cada gravação; `python -m
   netsentinel.api prune --confirm` também poda quadros.
4. **Dissecação no backend.** `netsentinel.packets.dissect` transforma bytes em
   camadas e campos com intervalo de bytes. O veredito usa `trusted_bindings()`,
   o mesmo inventário do detector; o frontend só desenha.
5. **Modal.** A seção "Pacotes ARP" lista os quadros; clicar abre um `<dialog>`
   com veredito, árvore de campos e bytes lado a lado, destaque cruzado,
   Anterior/Próximo e Esc. "Ver pacote" no histórico e no modal do dispositivo
   busca o quadro da detecção por `/api/packets/match`.

## Consequências

- O veredito do modal e a detecção não divergem: os dois leem o mesmo inventário.
- O volume é limitado nos dois sentidos (tempo e linhas), o que protege o plano
  gratuito do Supabase. Durante um ataque o limite de linhas chega antes dos 5
  dias: cerca de 30 min na nuvem sintética (10 quadros por segundo) e poucos
  minutos no laboratório a 50 pps. Detecção sem quadro guardado mostra essa
  mensagem em vez de outro pacote. A captura guarda no máximo 500 quadros por
  janela e conta o excedente em `arp_frames_dropped`.
- O veredito é sobre o vínculo IP→MAC declarado no quadro. Ele não substitui o
  score fuzzy, que também pesa frequência, reputação e desvio de volume.
- Sem PCAP, sem payload de outros protocolos e sem evento Socket.IO novo: a lista
  é atualizada na reconciliação REST disparada por `snapshot_updated`.
