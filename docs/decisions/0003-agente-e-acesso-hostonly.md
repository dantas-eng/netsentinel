# ADR 0003 — Agente da Vítima e acesso à demo

Status: aprovado pelo grupo; implementado para validação nas VMs na versão 0.3.0.

A VM do Sensor também hospeda o futuro backend/dashboard. Possui Internal Network
para captura e comunicação com a Vítima, e Host-only para acesso pelo navegador
do notebook. Não há quinta VM. O Sensor não encaminha IPv4/IPv6 entre interfaces,
não faz bridge/NAT e não tem rota default. Desativar ICS/compartilhamento/bridge
no host. Host-only não deve ser configurada com acesso externo.

O agente usa exclusivamente o IP interno da Vítima; autentica pelo peer TCP
igual ao IP Internal Network do Sensor e por token. O cliente vincula sua origem
a esse IP interno, sem proxies nem redirects. Não aceita X-Forwarded-For como
identidade. O futuro backend deve vincular sua interface de apresentação ao IP
Host-only; o agente nunca usa esse endereço como identidade do backend.

Na Vítima, nftables netdev/ingress bloqueia o MAC do Atacante. Uma tabela exclusiva
contém contadores antes do bloqueio, de descarte e depois da filtragem. A
associação ARP estática correta vem de configuração local. A API aceita somente
a ação fixa de mitigação e consulta de estado; não recebe comandos ou destinos.
MACs são validados sintaticamente e comparados com o Atacante autorizado.

O agente é serviço dedicado com CAP_NET_ADMIN. O journal identifica os recursos
criados, permite reinício e restauração local após parar o serviço. Contadores não
são zerados ao repetir a mitigação. Falhas parciais são expostas, sem sucesso falso.
A restauração preserva entradas estáticas preexistentes e remove apenas a tabela
e a entrada permanente criadas pelo NetSentinel, respeitando alterações externas.

O bloqueio por MAC cobre o cenário fixo do MVP; não promete resistir à troca de
MAC do atacante. HTTP sem TLS fica restrito ao laboratório aprovado, com token
fora do repositório. Testes offline não substituem a validação de filtragem no kernel,
configuração VirtualBox, queda/recuperação de ping e contadores reais.
