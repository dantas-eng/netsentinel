# Backend e dashboard 0.5.0 — operação e contratos

REST Flask, Socket.IO/Observer, repositories SQLAlchemy, calibração persistida e
sessão do operador implementados. O dashboard visual é servido em `/`.
O shell HTML, os assets, health, obtenção de CSRF e login são públicos;
os dados `/api/*` e Socket.IO exigem sessão autenticada. Login exige CSRF.

## Inicialização local

Preparar dependências antes de isolar as VMs:

```bash
python -m pip install -e '.[dev]'
```

Configurar as variáveis de `.env.example` no ambiente. O programa não carrega .env
implicitamente. Usar um banco SQLite em diretório gravável pelo usuário do backend,
segredo aleatório de pelo menos 32 caracteres e hash da senha do operador.
Gerar o hash localmente com `werkzeug.security.generate_password_hash`, lendo a
senha com getpass; não guardar senha ou hash real no repositório. O serviço opcional
lê `/etc/netsentinel/backend.env` via EnvironmentFile do systemd.

Na raiz do projeto, com o ambiente configurado:

```bash
python -m netsentinel.api migrate
python -m netsentinel.api bootstrap
python -m netsentinel.api serve
```

Executar bootstrap antes de começar a captura. Importa os três nós legítimos da
configuração como KNOWN se ainda não existirem. Registros existentes, inclusive
revogados, não são promovidos por reimportação. Usar confirmação manual pela API
quando um dispositivo já estiver registrado como NEW.

O modo lab exige LAB_CONFIG do Sensor (duas interfaces) e LAB_MAX_OBSERVATIONS.
O servidor vincula a porta ao IP **Host-only**, nunca a 0.0.0.0. Captura e conexão
com o agente usam a interface/IP **Internal Network**. O agente da Vítima deve
estar preparado, conforme lab/README.md, antes de testar mitigação.

A captura precisa de CAP_NET_RAW; o backend não precisa de CAP_NET_ADMIN.
`deploy/netsentinel-backend.service` configura essa capacidade, a migração antes
da inicialização e o diretório SQLite. Ajustar os caminhos ao instalar. Essa unit
não foi executada nas VMs neste ambiente. Não iniciar simultaneamente outro
executor `security.demo monitor`: cada ensaio deve ter uma única fonte/decisor.

A aplicação local usa Socket.IO com servidor de desenvolvimento sem debug,
restrito ao laboratório. O notebook acessará HTTP no IP Host-only/porta configurada.
Abrir `http://<IP-Host-only-do-Sensor>:<PORT>/` no notebook. A raiz serve
a tela de login e o dashboard. Assets já compilados acompanham o projeto;
o laboratório não usa CDN, fontes externas nem Node em runtime.
O fluxo visual e os testes do frontend estão descritos em `docs/dashboard.md`.

## Sessão e CSRF

**POST /api/auth/login também exige CSRF**, mesmo sem autenticação prévia.
Isso é intencional: o frontend deve primeiro fazer **GET /api/auth/csrf**
(rota pública), guardar `csrf_token` e preservar o cookie recebido. Só então
pode enviar **POST /api/auth/login** com `X-CSRF-Token` no header.
Enviar login diretamente, sem esse passo, retorna **403 csrf_required**;
não é um defeito da autenticação. Após o login, substituir o token em memória
pelo novo `csrf_token` da resposta, inclusive para autenticar Socket.IO.


1. GET `/api/auth/csrf`, preservando o cookie recebido.
2. POST `/api/auth/login` com JSON `{username,password}` e header X-CSRF-Token.
3. Preservar a sessão; usar o **novo** csrf_token devolvido pelo login.
4. Em todas as alterações, enviar o header X-CSRF-Token com esse token.
5. POST `/api/auth/logout` encerra sessão e desconecta seus clientes Socket.IO.

Lab: Secure=False explicitamente, HttpOnly=True, SameSite=Lax. Cloud: Secure=True,
exigindo HTTPS no navegador. A sessão expira após uma hora. O token de operador é
independente do token do agente da Vítima; nunca enviar o token do agente ao browser.

## REST

| Método/caminho | Função |
| --- | --- |
| GET /health | Verifica acesso ao schema e informa modo |
| GET /api/auth/session | Operador atual |
| GET /api/status | Estado da fonte e instante do último snapshot |
| GET /api/devices | Reputação, risco atual, baseline em bytes/s e datas |
| POST /api/devices/{mac}/reputation | `{known: boolean, reason: string}`; confirmação/revogação auditada |
| POST /api/devices/{mac}/calibrations | Inicia coleta explícita; retorna 202 e calibration_id |
| GET /api/devices/{mac}/calibrations | Estado e amostras persistidas |
| GET /api/topology | Nós persistidos e conexões observadas na última janela |
| GET /api/events?after_id=0&limit=100 | Histórico crescente, até 500 por página |
| GET /api/audit | Últimas 100 ações auditadas |

Erros: 401 sem sessão/credencial inválida, 403 sem CSRF, 409 para conflitos de
estado (ex.: calibração de NEW), 503 quando o Repository não está disponível.
`/health` indica banco acessível; consultar `/api/status` para saber se a fonte está
rodando. Após uma falha da fonte, reiniciar o processo depois de resolver a causa.

A confirmação não promete benignidade. UNKNOWN é falha do provider; MAC ausente
em consulta bem-sucedida e primeiro registro persistido são NEW. A API não permite
cadastrar UNKNOWN como estado administrativo.

## Baseline

São necessárias cinco janelas válidas de 8 s posteriores à solicitação, sem
sobreposição. A coleta demanda pelo menos 40 s, pode demorar mais por alinhamento,
conflitos ou perdas. Iniciar na preparação da demo com tráfego legítimo controlado.
Uma fonte parada não produz baseline. Fonte reiniciada interrompe a coleta.

Cada amostra guarda bytes e bytes/8. Mediana zero fica NULL e chega ao fuzzy como
input ausente, com pertinências zero. O valor anterior permanece durante uma
recalibração e é trocado apenas quando ela termina. Ver ADR 0005.

## Observer e reconexão

Conectar um cliente Socket.IO compatível com a série 4 do protocolo cliente,
enviando `auth: {csrf_token: tokenAtual}` e a sessão HTTP do mesmo domínio.
Não usar WebSocket puro: Socket.IO inclui seu próprio protocolo.
O servidor suporta transporte WebSocket via Flask-SocketIO/simple-websocket.
Não há handlers de alteração de dados pelo socket.

Eventos existentes são preservados:

- risk_evaluated: mantém attacker/false_gateway_claim e acrescenta devices, por MAC.
- mitigation_applied e mitigation_status: preservam evidence do agente.
- mitigation_error: mantém a informação de tentativa posterior.

Eventos adicionais: snapshot_updated, reputation_changed, baseline_calibrated,
source_error. Todos recebem event_id, timestamp e source (`live` ou `synthetic`).
O Repository faz commit antes do EventBus notificar os assinantes. Uma falha de
assinante não desfaz o evento nem impede os demais.

Ao reconectar, assinar os eventos e consultar `/api/events?after_id=ultimoId`,
deduplicando por event_id. O histórico tem paginação crescente; continuar pelo
último ID recebido até esgotar a página. Eventos não têm retenção automática
nesta versão; dimensionar o disco do laboratório e preservar a evidência da demo.

## Cloud, separado do laboratório

APP_MODE=cloud; DATABASE_URL Postgres, credenciais de operador e SECRET_KEY; sem
LAB_CONFIG. A fonte é sintética e não importa captura Scapy nem constrói cliente
do agente real. Ações sintéticas incluem `simulated:true` na evidência e não são
prova de mitigação. O banco cloud deve ser separado do banco local.

Após migração e bootstrap explícitos, entrada preparada para Gunicorn:

```bash
python -m gunicorn --workers 1 --threads 8 --bind 0.0.0.0:8080 \
  'netsentinel.api.wsgi:create_service()'
```

Ajustar a porta ao PORT do Cloud Run na etapa de deploy. Exige HTTPS no acesso
externo. **Um worker e uma instância** nesta implementação: fonte e EventBus são
locais ao processo. Não configurar múltiplas réplicas sem coordenação de fonte,
sessões e mensagens. Dockerfile e Compose foram adicionados na versão 0.6.0. CI/CD de publicação e
configuração final de Cloud Run/Postgres continuam para a etapa de deploy; nada foi publicado aqui.

## Verificação

```bash
python -m ruff check .
PYTHONPATH=src python tests/run_offline.py
```

101 testes Python aprovados; Ruff sem apontamentos. O frontend acrescenta
9 testes JavaScript (`cd frontend` e `npm test`) e build local de assets. SQLite real cobre persistência após
reabertura, reputação, auditoria, calibração e migrations. O teste Alembic compara
o schema criado com os modelos; também gera SQL PostgreSQL offline.

A integração usa PCAP/Scapy, Repository SQL, Mamdani, Strategy, API do agente e
Socket.IO test_client. O kernel do agente e a conexão HTTP com ele são simulados.
O teste de sessão verifica cookies HTTP com o test_client Flask. Ainda falta
ensaio de browser/WebSocket sobre rede, PostgreSQL real, VirtualBox e nftables.

Referências: https://flask-socketio.readthedocs.io/en/latest/getting_started.html
https://docs.sqlalchemy.org/en/20/orm/session_basics.html
https://alembic.sqlalchemy.org/en/latest/batch.html


## Container sintético (0.6.0)

Dockerfile/Compose e instruções para Windows em `docs/docker.md`. O entrypoint
faz migração antes de iniciar a factory cloud em Gunicorn, com um worker.
Docker/Compose, Postgres real e browser ainda não foram validados neste ambiente.
O critério de disparo da defesa agora exige duas avaliações consecutivas (ADR 0007).
