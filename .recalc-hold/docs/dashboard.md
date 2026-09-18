# Dashboard 0.7.0

## Operação

O Flask serve a interface em `/`, no mesmo endereço do backend. Usar o IP
Host-only do Sensor no notebook; o backend mantém o IP Internal Network para
contatar o agente. Nenhuma nova VM, ponte ou rota entre laboratório e nuvem.
Inicialização e ambiente estão em `backend.md`. O modo cloud continua exigindo
HTTPS e usando dados sintéticos; nenhuma publicação foi feita nesta etapa.

O login implementa GET `/api/auth/csrf` antes de POST `/api/auth/login`, preserva
cookies e envia X-CSRF-Token. Depois substitui o token pelo devolvido no login.
O token fica em memória, sem localStorage. Sessão existente é consultada ao abrir
a página. Logout limpa a tela e desconecta Socket.IO; respostas em trânsito de
uma sessão anterior não repovoam os dados. Falhas de login/CSRF/banco/rede são
exibidas; não são substituídas por dados de demonstração.

## Telas e contratos

| Parte | Dados e comportamento |
| --- | --- |
| Topologia | `/api/topology`; vis.js Network com nós identificados por MAC, cores da classificação recebida e conexões Ethernet observadas. Destinos sem origem observada e broadcast não recebem reputação inventada. Seleção abre detalhes quando existe registro no inventário. |
| Dispositivos | `/api/devices`; score de risco, classificação, reputação manual, última observação e baseline em bytes/s. Score nulo permanece sem avaliação. |
| Detalhes | Inputs do fuzzy, motivo do score nulo, confirmação/revogação com motivo e calibração via rotas existentes. Calibração mostra janelas aceitas de 0 a 5 e estado. Três superfícies novas no modal: (1) **Evidência observada** — protocolos, IPs reclamados e, quando finita, proporção de replies ARP, com nota de que protocolos/IPs não entram na inferência; (2) **Score no tempo** — sparkline de `GET /api/devices/<mac>/history?limit=200`, limiares 35/65 e empty-state textual; (3) **motivo do calibrate** desabilitado em `#calibrate-reason` (reputação, coleta em andamento ou fonte parada). |
| Eventos | `/api/events` paginado e Socket.IO; até 200 registros mais recentes, mais novo primeiro, detalhes JSON expansíveis. Ordenação/deduplicação por event_id, não pelo relógio do navegador. |
| Auditoria | `/api/audit`; até 100 ações mais recentes com operador, MAC, motivo e instante. |
| Estado | `/api/status`; ambiente, fonte em execução/parada, erro, janela de 8 s e última captura. Após duas janelas sem atualização, a interface alerta sobre dados antigos. Esse indicador não muda os parâmetros do motor. |
| Defesa | `mitigation_applied` / `mitigation_status`; MAC alvo, ARP estático, bloqueio e contadores. Erro posterior impede que as leituras históricas aparentem estado confirmado atual. |

Não há Vitals, ranking de consumo, GA ou execução manual de ataque no browser.
A confirmação de reputação não é uma classificação de risco; dispositivos
reconhecidos continuam sujeitos ao fuzzy. O frontend não calcula um score novo.

## Atualizações e reconexão

O cliente usa Socket.IO série 4 com transporte WebSocket e autenticação
`auth: {csrf_token}`. Escuta `risk_evaluated`, `threat_unmitigable`,
`mitigation_applied`, `mitigation_status`, `mitigation_error`,
`reputation_changed`, `baseline_calibrated`, `snapshot_updated` e `source_error`.

Conexão, reconexão e notificações provocam reconciliação REST dos dados e
recuperação dos eventos pendentes. Chamadas concorrentes são agrupadas. O cursor
só avança com páginas REST; receber um ID maior por Socket.IO não pula eventos
que ainda faltam. O histórico retido na tela tem limite de 200 itens; o banco
continua sendo a fonte de histórico. No primeiro acesso o replay começa em zero.
Isso é adequado ao ensaio MVP, mas um banco com muitos eventos aumenta o tempo
de carga inicial. O modal lê a série de score em `GET /api/devices/<mac>/history`;
isso não substitui o replay paginado de `/api/events`.

Não há polling periódico de endpoints. O timer local apenas atualiza o aviso de
idade da captura. Desconexão é visível; o botão Atualizar permite tentar conexão
e leitura novamente. Transporte WebSocket indisponível não vira silenciosamente
um indicador de tempo real. Não se implementou escala para múltiplas instâncias.

## Evidência e limites

O painel compara as duas últimas leituras de mitigação por ordem de registro:

- mostra valores anteriores, atuais e deltas de `seen`, `dropped` e `passed`;
- não compara como válido um intervalo com agente/alvo diferente, mistura de
  simulação e execução real, timestamp não crescente, contador ausente ou reset;
- aponta explicitamente ausência de tráfego/descartes e entrega após o filtro;
- não declara ping verificado: queda e recuperação devem ser observadas no
  terminal da Vítima, enquanto os contadores e o ARP estático provam as outras camadas.

Esses dados são uma apresentação das leituras, não uma nova ação do agente.
A verificação formal do intervalo continua disponível no comando de segurança
`verify`. No modo sintético, o painel traz aviso de que não comprova defesa real.
A presença de uma aresta no Sensor passivo não comprova entrega após o firewall.

## Assets e contribuição

Stack preservada: Flask, JavaScript puro, Tailwind e vis.js Network. Os fontes são
`templates/dashboard.html`, `static/dashboard.mjs` e `static/core.mjs` no pacote
`netsentinel.api`; Tailwind e script de build ficam em `frontend/`.
`npm ci` usa o lockfile; `npm run build` compila CSS e copia bundles/licenças para
`static/`. Assets versionados permitem uso sem Node/CDN/internet no laboratório.
As versões diretas ficam registradas em `static/vendor/versions.json`.
Conteúdo recebido é inserido com textContent, não como HTML executável.

## Validação desta entrega

- **148 testes Python e Ruff aprovados** (`tests/run_offline.py` → `Ran 148 tests`):
  preservam os testes anteriores e cobrem CSP no header HTTP, corpus de evidência,
  histórico, poda e detecção ampla.
- **14 testes JavaScript aprovados** (`cd frontend && npm test` → `# pass 14`):
  CSRF, replay, grafo, `counterInterval`/`reason_code`, corpus compartilhado e
  `sparkline`.
- **CSP no header:** `Content-Security-Policy` com `default-src 'self'` e
  `script-src 'self'` é devolvido por Flask e exercitado nos testes de integração.
  A checagem visual no navegador (grafo, console sem violação CSP, status
  `Eventos conectados` e seções novas do modal) **não foi refeita** nesta
  atualização: a imagem Docker em `:8080` estava desatualizada.
- **Build e sintaxe aprovados:** Tailwind, cópia dos bundles e `node --check` nos
  módulos; CI recebeu job frontend. O workflow ainda não rodou em GitHub real.

Não houve revalidação visual ou interação em navegador nesta atualização,
nem PostgreSQL real nem ensaio das VMs.
Os testes JavaScript usam funções puras e fetch simulado; Flask/Socket.IO usam
os clientes de teste existentes. Não confundir esses resultados com a demo ao vivo.

Na validação das VMs: abrir no notebook, verificar login HTTP e reconexão,
reconhecimento/calibração e grafo, depois acompanhar ping, ARP e contadores no
ataque sem encaminhamento. A coleta real e a mitigação continuam restritas à
rede isolada autorizada. Postgres real e Cloud Run pertencem à etapa de deploy.

Referências de implementação:
[vis.js Network](https://visjs.github.io/vis-network/docs/network/),
[cliente Socket.IO](https://socket.io/docs/v4/client-options/),
[Tailwind CLI](https://tailwindcss.com/docs/installation/tailwind-cli).
