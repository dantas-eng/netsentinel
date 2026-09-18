# Demo ARP — quatro VMs Linux no VirtualBox

Roteiro atualizado para a versão 0.6.0: cenário, agente, backend e dashboard
implementados. Validação ao vivo ainda pendente. Não executar estes comandos no host ou em redes de terceiros.

## Topologia e configuração

| VM | Adaptadores | Função |
| --- | --- | --- |
| Atacante | Internal Network | Envenena ARP sem encaminhar |
| Vítima | Internal Network | Ping e agente de mitigação |
| Gateway | Internal Network | Destino interno do ping, sem uplink |
| Sensor | Internal Network + Host-only | Captura e backend/dashboard com SourceRunner |

Mesmo nome de Internal Network nos quatro adaptadores internos. No Sensor:
**Promiscuous Mode = Allow All** no adaptador interno. Desativar os demais
adaptadores de Atacante/Vítima/Gateway. Sem NAT, bridge, rota default ou internet.
A Host-only conecta somente o notebook ao Sensor; não deve haver ICS,
compartilhamento de internet ou bridge no notebook. Usar IPs estáticos, sem gateway
padrão. Desativar encaminhamento IPv4/IPv6 em Sensor e Atacante (o agente também
verifica isso na Vítima). O arquivo `deploy/90-netsentinel-no-forwarding.conf`
serve de configuração sysctl para as VMs dedicadas; confirmar os valores por
interface após aplicar, pois as verificações recusam qualquer forwarding ativo.

Os arquivos `*.example.json` são exemplos completos. Ajustar IPs, MACs e nomes de
interface ao VirtualBox, sem inferir o MAC legítimo do Gateway pelo tráfego durante
o ataque. As três cópias devem concordar nos quatro nós; `interface` é o nome
local de cada VM. Configuração real vai em `/etc/netsentinel/lab.json` em cada nó.
Host-only é declarada somente na cópia do Sensor. Não publicar token nem config
real no repositório. O Gateway não precisa executar código NetSentinel.

O preflight verifica interfaces extras, bridge/master, IP/MAC do papel, rotas
default e forwarding. Ele não consegue comprovar o modo do adaptador VirtualBox
nem a configuração ICS do notebook. Conferir isso manualmente antes do ensaio.
Bridges padrão do Docker também conflitam com estas condições: esta etapa é
executada diretamente nas VMs. A rede do ataque real em Docker ainda exige validação própria; o Compose
sintético de `docs/docker.md` é separado e não substitui estas quatro VMs.

## Dependências e instalação

Linux com systemd, iproute2 (`ip`), nftables (`nft`), Python 3.11+ e permissão para
configurar netdev/ingress. Preparar os pacotes antes do isolamento, ou transferir
pacotes/wheels offline. Código em `/opt/netsentinel`, ambiente em `.venv`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Na Vítima, criar usuário de serviço `netsentinel` sem login. Configuração e código
devem ser administrados pelo responsável pela VM; o usuário do agente precisa
ler a configuração/token e escrever somente em `/var/lib/netsentinel`. Copiar
`deploy/netsentinel-agent.service` para `/etc/systemd/system/`. Os caminhos da unit
pressupõem a instalação indicada; ajustar se o grupo escolher outros caminhos.

Gerar um token aleatório de 32 bytes, codificado como 64 dígitos hexadecimais, e
copiar offline **somente para Vítima e Sensor**, no caminho `token_file`. Pode-se
usar `secrets.token_hex(32)`. Arquivo na Vítima: proprietário root, grupo
netsentinel, modo 0640. No Sensor, acesso apenas ao usuário que executa o cliente.
Não colocar o token em URLs, configs JSON, logs ou argumentos de terminal.
O Atacante e o Gateway não precisam do token.

A unit usa CAP_NET_ADMIN para `ip`/`nft`, sem CAP_NET_RAW ou root no agente. Captura
e envio Scapy nos nós respectivos precisam de acesso a sockets raw; os exemplos
abaixo usam sudo exclusivamente nessas VMs dedicadas.

## Ambiente do operador no Sensor

Antes do ensaio, preparar `/opt/netsentinel/.env` a partir de `.env.example`,
sem versionar os valores reais. Gerar o hash da senha com Werkzeug, usando o
Python do projeto. A senha é digitada sem eco e não fica no histórico do shell:

```bash
.venv/bin/python -c 'from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass("Senha do operador: ")))'
```

Copiar o resultado para `OPERATOR_PASSWORD_HASH` no `.env`, **entre aspas simples**
para preservar os caracteres `$` ao carregar o arquivo pelo shell:

```dotenv
OPERATOR_PASSWORD_HASH='COLE_AQUI_O_HASH_GERADO'
```

Preencher também APP_MODE=lab, DATABASE_URL, SECRET_KEY, OPERATOR_USERNAME,
LAB_CONFIG, LAB_MAX_OBSERVATIONS e PORT conforme `.env.example`. SECRET_KEY deve
ser aleatório e ter pelo menos 32 caracteres. A credencial do operador é diferente
do token do agente. Proteger o `.env` com modo 0600, acessível ao responsável pelo
backend; não compartilhar senha, hash ou segredo nas evidências da apresentação.
O diretório do SQLite deve existir e ser gravável pelo usuário do backend.

**A aplicação não carrega `.env` automaticamente.** No terminal do Sensor, na
raiz `/opt/netsentinel`, exportar as variáveis do arquivo local confiável:

```bash
source .venv/bin/activate
set -a
source .env
set +a
```

Manter esse ambiente para os comandos de migração, bootstrap e servidor abaixo.
Para instalação como serviço dedicado, `deploy/netsentinel-backend.service` usa
`/etc/netsentinel/backend.env` e CAP_NET_RAW; consultar `docs/backend.md`.
Não iniciar o serviço e um segundo `serve` simultaneamente.

## Sequência reproduzível de demonstração

1. **Vítima, antes do ataque:** garantir que a entrada do Gateway não esteja
   PERMANENT de um ensaio anterior. Uma entrada estática já correta impede o
   envenenamento por design. O agente preserva entradas preexistentes; não as
   remove silenciosamente. Usar estado inicial controlado da VM para a demo.
2. **Vítima:** iniciar o agente antes do envenenamento:

```bash
sudo systemctl daemon-reload
sudo systemctl start netsentinel-agent
sudo systemctl status netsentinel-agent
```

3. **Sensor:** verificar as condições locais:

```bash
.venv/bin/python -m netsentinel.security.demo preflight --config /etc/netsentinel/lab.json
```

4. **Vítima:** iniciar `ping IP_INTERNO_DO_GATEWAY` e deixá-lo visível durante todo
   o ensaio. Confirmar respostas antes do ataque.
5. **Sensor:** conferir o ambiente do operador descrito acima, o diretório do
   SQLite e o acesso ao token do agente. Confirmar que não há outro processo de
   captura/decisão (`security.demo monitor`, outro `serve` ou serviço backend)
   executando em paralelo.
6. **Sensor, antes do ataque:** na preparação inicial deste banco, executar uma
   vez a migração e o bootstrap explícito do inventário legítimo:

```bash
python -m netsentinel.api migrate
python -m netsentinel.api bootstrap
```

Executar bootstrap antes da primeira captura: registra Gateway, Vítima e Sensor
como KNOWN quando ainda não existem. Não promove registros existentes nem desfaz
revogação. O Atacante continua NEW. Não é necessário repetir bootstrap a cada
ensaio; novas versões com migrações exigem executar `migrate` novamente.

Depois iniciar o executor real:

```bash
python -m netsentinel.api serve
```

Esse comando **já inicia o SourceRunner**, a captura, a classificação fuzzy com
Repositories persistidos, a defesa e o servidor do dashboard. A captura exige
CAP_NET_RAW. Se o terminal não tiver essa capacidade, o equivalente para execução
manual com sudo nesta VM dedicada, preservando somente as variáveis necessárias, é:

```bash
sudo --preserve-env=APP_MODE,DATABASE_URL,SECRET_KEY,OPERATOR_USERNAME,OPERATOR_PASSWORD_HASH,LAB_CONFIG,LAB_MAX_OBSERVATIONS,PORT \
  .venv/bin/python -m netsentinel.api serve
```

Escolher uma única forma de iniciar. Manter a propriedade/permissão dos arquivos
SQLite compatível com o usuário escolhido; não alternar execução manual e serviço
sem conferir esse acesso. LAB_MAX_OBSERVATIONS=10000 é exemplo de capacidade.
A janela de captura é de 8 segundos. O servidor vincula o endereço Host-only do
Sensor; a comunicação com o agente usa o IP Internal Network.

`security.demo monitor` continua disponível **somente como ferramenta de depuração
sem dashboard**, com seus providers locais. Não é o caminho principal do ensaio
e não deve rodar junto com o backend. Os comandos `preflight` e `verify` continuam
sendo ferramentas auxiliares válidas.

7. **Notebook, antes do ataque:** abrir
   `http://IP_HOST_ONLY_DO_SENSOR:PORT/` (PORT padrão 8080), fazer login com a
   credencial do operador e confirmar eventos conectados, fonte em execução e
   captura atualizada. A tela faz GET `/api/auth/csrf` antes de POST
   `/api/auth/login`, enviando X-CSRF-Token; o cookie permite HTTP no laboratório.
   Conferir dispositivos e topologia. Os assets são locais, sem necessidade de
   internet. Manter o dashboard e o ping da Vítima visíveis.
8. **Atacante:** iniciar o cenário limitado. Os números abaixo são parâmetros de
   ensaio (10 anúncios/s, máximo 120 s), ajustáveis após medição:

```bash
sudo .venv/bin/python -m netsentinel.security.attack \
  --config /etc/netsentinel/lab.json --pps 10 --seconds 120
```

O comando exige forwarding desligado e o verifica novamente durante a execução.
Só envia ARP replies unicast à Vítima, alegando o IP do Gateway com o MAC do
Atacante. Não habilita forwarding nem instala NAT. Ctrl+C encerra o envio. Não
executar outro processo de relay no Atacante. Limites locais: até 50 anúncios/s e
300 s por execução; a taxa efetiva pode ser menor devido ao custo do envio/checks.

O backend aplica fuzzy e exige, além de score >=65, uma alegação falsa do IP
conhecido do Gateway originada no MAC do Atacante configurado. Só então chama
VictimAgentMitigationStrategy, após **duas avaliações consecutivas** qualificando
para o mesmo MAC (ADR 0007). Uma avaliação não qualificante zera a contagem.
Isso não é atribuição genérica de autoria pelo score.
Reputação e baseline vêm dos Repositories persistidos; baseline só fica disponível
após calibração válida, iniciada explicitamente para um dispositivo KNOWN.

**Ponto a medir no ensaio:** com `serve` já iniciado para permitir login antes do
ataque, a defesa é automática e pode agir antes de uma perda de ping ficar visível.
A ADR 0007 exige duas avaliações consecutivas, mas isso não equivale a duas
janelas de 8 s independentes nem garante um atraso fixo. Não há pausa ou botão
de armar defesa nesta versão. Registrar o tempo até mitigação
e verificar se ocorre a queda/recuperação exigida. Se não ocorrer, o critério visual
continua pendente e o grupo deve discutir o ajuste antes da demo; não afirmar que
este fluxo garante interrupção perceptível nem usar o executor antigo em paralelo.

9. **Vítima:** observar recuperação do ping após `mitigation_applied`. Deixar o
   Atacante enviando para medir descartes; interrompê-lo antes disso torna a
   evidência inconclusiva.
10. **Outro terminal no Sensor:** medir um intervalo posterior à defesa:

```bash
.venv/bin/python -m netsentinel.security.demo verify \
  --config /etc/netsentinel/lab.json --evidence-seconds 5
```

Exige delta positivo de `seen` e `dropped`, delta zero de `passed`, bloqueio ativo
e ARP permanente correto nas duas consultas. O código de saída é 0 somente se
essas condições forem confirmadas. Não marca ping como verificado automaticamente.
Registrar a tela do ping, JSON de evidência e a consulta local de ARP:

```bash
ip -j neigh show
```

Contadores representam quadros do MAC configurado na interface da Vítima:
`seen` antes do bloqueio, `dropped` na regra de descarte e `passed` em uma chain
posterior. Não exigir `passed` total zero: ele pode ter aumentado antes da defesa.
A avaliação usa deltas do mesmo run_id. Reinício/recriação de tabela ou contadores
regredindo tornam a comparação inválida. As leituras dos contadores não são uma
amostragem atômica de todos os pacotes, por isso não se exige seen == dropped.

O `netdev ingress` ocorre depois dos taps de captura; Scapy/tcpdump podem continuar
vendo quadros descartados. `passed` mede passagem após nosso filtro, não entrega
à aplicação. Zero incremento com tráfego ativo demonstra bloqueio nesse ponto.
O Sensor pode continuar vendo todo o envio do Atacante.

## Restauração do ensaio

Parar primeiro Atacante e backend no Sensor (`serve`: Ctrl+C; se iniciado como
serviço, parar `netsentinel-backend`), depois o agente na Vítima.
Na Vítima:

```bash
sudo systemctl stop netsentinel-agent
sudo /opt/netsentinel/.venv/bin/python -m netsentinel.security.agent restore \
  --config /etc/netsentinel/lab.json
```

Remove somente `netdev netsentinel_lab` com marker/journal correspondente e a
entrada permanente que o agente criou. Uma entrada permanente já correta antes
do ensaio é preservada. Entradas dinâmicas antigas não são reproduzidas: serão
reaprendidas após parar o ataque. Alteração estática externa divergente interrompe
a restauração para não sobrescrevê-la. Sem journal, o código não remove tabela
existente. Não apagar journal manualmente para contornar essa proteção.
A operação é repetível; segunda execução após limpeza retorna `already_clean`.

## API e rede de apresentação

- `POST /v1/mitigations`: JSON contendo somente `attacker_mac` autorizado.
- `GET /v1/status`: bloqueio, ARP, contadores, timestamp e run_id.
- Ambas exigem token Bearer e peer TCP igual a **sensor_internal_ip**.
- O agente não confia em X-Forwarded-For; não há endpoint de comandos/restauração.
- Erros parciais retornam 503; consulta de status permite ver qual camada falhou.
- Retentativas não zeram contadores nem criam regras duplicadas.

O dashboard é acessado no navegador do notebook pelo IP **Host-only do Sensor**.
O backend está disponível desde a versão 0.4.0 e a interface visual desde a 0.5.0.
Para chamar o agente, VictimAgentMitigationStrategy vincula a conexão ao IP
**Internal Network** do Sensor, nunca ao endereço Host-only. O dashboard mostra
eventos, reputação, baseline e evidências; ping continua sendo observado na Vítima.

## Limites da validação atual

Testes offline usam Scapy e Mamdani reais, Flask test_client e kernel substituto.
Não comprovam sintaxe aceita pela versão nft instalada, filtragem no kernel,
CAP_NET_ADMIN sob systemd, modo VirtualBox ou queda/recuperação real de ping.
Esses pontos exigem o ensaio nas VMs. Não afirmar demo validada até completá-lo.
Antes da banca, medir anúncios/s reais e verificar a alegação do Gateway na janela.
Conflito pode ser zero: a R2 cobre o Atacante NEW sem baseline pela frequência.

Referências de implementação:
- https://netfilter.org/projects/nftables/manpage.html
- https://man7.org/linux/man-pages/man8/ip-neighbour.8.html
