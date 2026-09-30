# Ensaio de aceitação — quatro VMs

Executar apenas nas VMs dedicadas do grupo. Este documento é uma lista de
aceitação; instalação, arquivos e sequência operacional completos estão em
[lab/README.md](../../lab/README.md). Não conectar o laboratório ao deploy cloud.

## A. Preparar antes do isolamento

1. Escolher uma mesma distribuição Linux suportada e preparar VirtualBox,
   Python 3.11+, venv, iproute2, nftables e systemd. Instalar dependências do
   projeto e, se usado para evidência, tcpdump **antes** de isolar as VMs.
2. Copiar o mesmo commit para `/opt/netsentinel` nos nós que executam código.
   O Gateway só precisa responder ao ping. Anotar commit, versões do kernel,
   nftables e VirtualBox na ficha de evidências.
3. Preparar snapshots limpos das VMs para repetição controlada. Registrar os MACs
   efetivos pelo VirtualBox/console; não descobrir o MAC confiável pelo tráfego
   durante o ataque. Ajustar os exemplos JSON a esses valores.
4. Preparar usuário/serviço do agente, token apenas em Vítima/Sensor e credencial
   do operador no Sensor conforme o lab/README. Gerar hash Werkzeug, não salvar
   senha em texto no JSON. Preparar diretório SQLite e permissões.

## B. Conferir topologia

| Nó | Rede interna de exemplo | Adaptadores |
|---|---|---|
| Gateway | 10.77.0.1/24 | Somente Internal Network |
| Vítima | 10.77.0.20/24 | Somente Internal Network |
| Atacante | 10.77.0.30/24 | Somente Internal Network |
| Sensor | 10.77.0.40/24 e Host-only 192.168.56.40/24 | Internal Network + Host-only |

São exemplos dos arquivos existentes, não inventário confirmado do notebook.
Usar o mesmo nome de Internal Network. No adaptador interno do Sensor, configurar
Promiscuous Mode = **Allow All**. Nenhuma VM mantém NAT/bridge/uplink; nenhuma
rota default. Host-only sem ICS/ponte no Windows. Encaminhamento IPv4/IPv6
desligado em todos os nós; Gateway é um destino local, não roteia para internet.

No Linux, conferir `ip -br addr`, `ip route`, `ip -6 route` e os sysctls de
forwarding. Aplicar a configuração fornecida em deploy/ conforme lab/README.
No Sensor:

```bash
/opt/netsentinel/.venv/bin/python -m netsentinel.security.demo preflight \
  --config /etc/netsentinel/lab.json
```

Se falhar, corrigir topologia/configuração; não remover a verificação do código.
O preflight não comprova sozinho o modo VirtualBox nem o ICS do Windows.

## C. Executar e registrar

1. Vítima: verificar ausência de regra/ARP permanente restante de ensaio anterior.
   Usar restauração oficial, não apagar journal ou tabela nft manualmente.
2. Vítima: iniciar `netsentinel-agent`, conferir serviço e iniciar ping contínuo
   ao Gateway. Registrar respostas antes do ataque.
3. Sensor: carregar `.env` explicitamente como no lab/README; executar `python -m
   netsentinel.api migrate` e `bootstrap` na preparação inicial do banco. Iniciar
   `serve` com CAP_NET_RAW, preferencialmente pelo serviço dedicado já fornecido.
   Não executar `security.demo monitor` em paralelo: ele é só depuração.
4. Notebook: abrir dashboard pelo Host-only, fazer login e conferir fonte/topologia
   antes do ataque. Não usar URL Render para representar esse ambiente.
5. Atacante: executar o cenário aprovado **sem forwarding**:

```bash
sudo /opt/netsentinel/.venv/bin/python -m netsentinel.security.attack \
  --config /etc/netsentinel/lab.json --pps 10 --seconds 120
```

6. Registrar ping falhando, eventos/risco e posterior recuperação. A defesa exige
   duas avaliações consecutivas qualificantes para o mesmo MAC, mas não duas
   janelas independentes de 8 s. Se a defesa for rápida demais para ver a queda,
   marcar o critério visual como não atendido e discutir ajuste; não fabricar
   resultado, pausar o agente secretamente ou iniciar executor antigo.
7. **Manter o ataque ativo após a defesa** e, em outro terminal no Sensor:

```bash
/opt/netsentinel/.venv/bin/python -m netsentinel.security.demo verify \
  --config /etc/netsentinel/lab.json --evidence-seconds 5
```

8. Vítima: guardar `ip -j neigh show` e, com privilégio administrativo, a saída
   de `nft list table netdev netsentinel_lab`. Conferir MAC legítimo e estado
   permanente do Gateway; contadores do mesmo run_id.
9. Sensor: comprovar recebimento de unicast Atacante→Vítima, pelo registro da
   captura e/ou tcpdump instalado previamente. Filtrar a interface interna e os
   MACs efetivos; guardar captura curta e sanitizada. O Sensor ver o envio após
   a defesa é esperado e não significa que o firewall falhou.

## D. Critério de aprovação

| Verificação | Deve acontecer |
|---|---|
| Isolamento | Sem NAT/uplink/roteamento; configs e papéis corretos |
| Visibilidade | Sensor recebe unicast entre outros nós na Internal Network |
| Interface | Login e atualização ao vivo pelo Host-only |
| Antes/durante/depois | Ping responde, falha no envenenamento e recupera após defesa |
| Defesa | Entrada ARP permanente correta e bloqueio ativo |
| Evidência de filtro | Mesmo run_id; delta seen > 0, dropped > 0, passed = 0 |
| Repetição | Restauração permite novo ensaio controlado sem resíduos indevidos |

`passed` total pode ser positivo por tráfego anterior: usar delta posterior à
defesa. Os taps de captura podem observar quadros depois descartados por ingress;
ausência de pacotes no tcpdump não é o critério de filtragem. Ping sozinho também
não basta. Registrar duração até mitigação, taxa ARP efetiva e se o Gateway fez
alegação ARP na mesma janela. Ausência dessa alegação pode zerar conflito; não
alterar dados para ocultá-la.

## E. Restaurar

Parar ataque e backend primeiro. Na Vítima:

```bash
sudo systemctl stop netsentinel-agent
sudo /opt/netsentinel/.venv/bin/python -m netsentinel.security.agent restore \
  --config /etc/netsentinel/lab.json
```

Conferir o resultado; entrada permanente preexistente é preservada por design.
Se houver divergência externa de estado, investigar antes de repetir. Não apagar
o journal para forçar remoção. Guardar evidência de restauração e repetir a
sequência para confirmar reprodutibilidade. Atualizar compliance só após aprovação.
