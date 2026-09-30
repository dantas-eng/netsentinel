# Nuvem — Render Free + Supabase Free

Escolha aprovada pelo grupo em 28/09/2026; [ADR 0012](../decisions/0012-deploy-academico-gratuito.md).
Objetivo: mesma aplicação Docker, somente dados sintéticos, HTTPS e CI/CD real.
O procedimento exige contas do grupo e internet no notebook, nunca nas VMs do lab.

## Gratuidade e limites

Condições oficiais consultadas em 28/09/2026:

| Serviço | Condições relevantes |
|---|---|
| Render Web Service Free | 750 horas/mês por workspace; pausa após 15 min sem tráfego; quotas de build/egress; filesystem efêmero |
| Supabase Free | 500 MB de banco, 5 GB de egress; até 2 projetos ativos; pode pausar após 1 semana sem uso |
| GitHub Actions em repo público | Usar runners hospedados padrão já existentes; não selecionar runners maiores/pagos |

Os números são limites de plano, não reserva exclusiva para este projeto.
Render pode suspender serviço com tráfego externo elevado. Sem método de pagamento,
excedentes de banda/build podem suspender serviço/build; com cartão podem gerar
cobrança conforme a conta. Preferir contas sem cartão, não aceitar upgrade e
interromper se a interface exigir plano pago. Não usar Render Postgres Free:
ele expira em 30 dias. Cloud SQL não faz parte desta configuração.

Não configurar monitor que envie pings só para impedir suspensão. Antes de uma
apresentação, abrir o serviço com antecedência e conferir se o Supabase está ativo.
A primeira abertura do Render pode levar cerca de um minuto. A demonstração
principal do ataque continua local nas VMs, independente desses serviços.

## A. Preparar o banco (grupo, uma vez)

1. Criar/usar conta Supabase e organização **Free**. Criar um projeto dedicado
   `netsentinel`, com senha forte de banco guardada pelo grupo. Escolher região
   próxima da região disponível para o Web Service; não comprar add-on IPv4.
2. Em **Data API / Integration**, desligar **Enable Data API**. O NetSentinel
   acessa Postgres via SQLAlchemy; não usa anon key, service_role ou APIs Supabase.
   Isso evita expor tabelas criadas pelo Alembic por uma API paralela sem sessão Flask.
3. Em **Connect**, escolher **Session pooler**, porta **5432**. Copiar a URL
   correspondente ao projeto. Não usar Transaction pooler/porta 6543: manter
   semântica de sessão e prepared statements do driver sem mudar o app.
4. Usar a URL no formato abaixo; substituir todos os campos ilustrativos:

```text
postgresql+psycopg://postgres.PROJECT_REF:SENHA_CODIFICADA@HOST_DO_SESSION_POOLER:5432/postgres?sslmode=require&connect_timeout=10
```

Se a senha tiver caracteres reservados, codificá-la como componente de URL
(percent-encoding), não codificar a URL inteira. Não colocar aspas literais no
campo Environment do Render. O driver psycopg já está na imagem.

`sslmode=require` exige criptografia, mas não verifica identidade do servidor.
Para verificação completa, usar certificado/CA compatível com o endpoint,
montado como Secret File no Render, e `sslmode=verify-full&sslrootcert=CAMINHO`.
Não usar `sslmode=disable` para resolver falha de conexão.

## B. Criar o aplicativo (grupo, uma vez)

Antes de criar o serviço, integrar por PR os arquivos desta entrega e aguardar
a CI da main passar. O Render construirá o Dockerfile existente.

1. Criar conta/workspace Render gratuito e conectar o repositório GitHub do grupo.
2. **New → Web Service**, repositório NetSentinel, branch `main`, runtime **Docker**,
   Dockerfile `./Dockerfile`, contexto raiz, nome disponível, plano **Free**.
   Usar apenas **uma instância**. Não criar Background Worker nem disco persistente.
3. Health Check Path `/health`; manter CMD do Dockerfile, sem sobrescrever o
   comando de inicialização. Ele executa Alembic antes de Gunicorn, um worker.
4. Auto-Deploy **Off**: a publicação subsequente pertence ao GitHub Actions.
5. Preencher as variáveis abaixo. `render.yaml` é a especificação equivalente
   para quem optar por Blueprint. Nesse caso revisar o plano Free e desligar
   Auto Sync do Blueprint após a criação; alterações de infraestrutura devem
   ser revisadas manualmente, sem contornar os checks do pipeline.

| Variável no Render | Valor |
|---|---|
| APP_MODE | `cloud` |
| PORT | `8080` |
| DATABASE_URL | URL do Session pooler, secreta |
| SECRET_KEY | Segredo aleatório de pelo menos 32 caracteres, fixo entre deploys |
| OPERATOR_USERNAME | `operador` ou nome escolhido |
| OPERATOR_PASSWORD_HASH | Hash Werkzeug completo da senha do operador |

**Não configurar LAB_CONFIG, token do agente ou IPs reais das VMs.**

No PowerShell, com a imagem local construída conforme docs/docker.md:

```powershell
docker run --rm netsentinel:local python -c "import secrets; print(secrets.token_hex(32))"
docker run --rm -it netsentinel:local python -c "from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass('Senha do operador CLOUD: ')))"
```

Primeira saída: SECRET_KEY. Segunda: OPERATOR_PASSWORD_HASH. Digitar a senha sem
eco e guardá-la: ela será usada no login e no secret do smoke. Nos campos web do
Render, colar o hash completo **sem aspas envolventes**; não é um arquivo shell.

6. Criar o serviço. Este bootstrap pode fazer o primeiro deploy automaticamente.
   Guardar a URL `https://NOME.onrender.com` e o Service ID `srv-...`.
7. Conferir logs: migração concluída e Gunicorn ativo; acessar `/health` e o login.
   Não há bootstrap de reputação automático: dispositivos cloud podem continuar
   NEW até confirmação explícita. Não alterar o cenário operacional para essa etapa.

## C. Ativar CD no GitHub

O workflow existente mantém os três jobs obrigatórios e acrescenta `Deploy
acadêmico Render`. Ele depende dos três e não executa em PRs.

1. Render Account Settings → API Keys: gerar uma chave para a automação.
2. GitHub → Settings → Environments: criar `academic-cloud`, restringindo
   deployment branches à **main**. Não cadastrar senha no código ou comentário.
3. Nesse environment, cadastrar **Secrets**:

| Secret | Conteúdo |
|---|---|
| RENDER_API_KEY | Chave de API Render |
| CLOUD_OPERATOR_PASSWORD | Senha de login em texto, não o hash; guardada como secret GitHub |

4. GitHub → Settings → Secrets and variables → Actions → **Variables** no
   repositório (não apenas no environment):

| Variable | Conteúdo |
|---|---|
| RENDER_SERVICE_ID | `srv-...` do aplicativo correto |
| CLOUD_URL | Origem HTTPS exata, sem caminho, query ou credenciais |
| CLOUD_OPERATOR_USERNAME | Mesmo nome configurado no Render |
| RENDER_DEPLOY_ENABLED | `true`, por último, após completar configuração |

A variável de ativação fica no repositório porque a condição do job é avaliada
antes da entrada no environment. Nenhuma credencial de banco vai para o GitHub.

5. Actions → **CI** → Run workflow → branch **main**. Os três jobs executam
   primeiro; o quarto envia o SHA completo, aguarda `live`, confere o commit e
   executa `tools/cloud_smoke.py`. O mesmo fluxo roda em novos pushes/merges na main.
6. Guardar URL do run, SHA e artefato `cloud-deploy-<SHA>`. O artefato só é enviado
   após smoke aprovado. `live` sozinho não certifica login e fonte saudável.

Não renomear nem remover os três checks já exigidos pela proteção da main.
Não tornar o job de deploy obrigatório em PR: nele o job é intencionalmente pulado.
Se houver falha/time-out, consultar o painel antes de reexecutar: o deploy remoto
pode continuar mesmo após o runner terminar. Nunca repetir POST às cegas.

## D. Validar banco gerenciado e navegador

No SQL Editor do projeto Supabase, executar consultas somente de leitura:

```sql
SELECT version_num FROM alembic_version;
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' ORDER BY table_name;
SELECT pg_size_pretty(pg_database_size(current_database())) AS database_size;
```

Comparar a revisão com `migrations/versions/` no commit implantado. Banco acessível,
revisão correta e smoke verde comprovam a migração e operação inicial; registrar
as saídas sem credenciais. Para futura mudança de schema, exportar backup antes;
rollback de código não desfaz migração automaticamente.

No navegador:

1. Abrir URL HTTPS em janela anônima: workspace oculto, API privada sem sessão.
2. Fazer login; recarregar a página e confirmar que a sessão persiste.
3. Conferir identificação de **dados sintéticos**, topologia, dispositivos,
   timeline e fonte atualizando. A simulação de ataque começa após cerca de 60 s;
   a ameaça adicional surge após cerca de 90 s desde a inicialização da fonte.
4. DevTools → Network: verificar Socket.IO e atualizações. Desconectar/reconectar
   o navegador e conferir recuperação do histórico via REST, sem duplicações.
5. Anotar um ID de evento, encerrar/reiniciar o serviço de forma controlada e
   confirmar persistência do histórico. Não confundir reinício do relógio sintético
   com perda de dados. Não coletar evidência/calibrar durante um redeploy.
6. Fazer logout e verificar que a API volta a responder 401.

Smoke adicional local, sem salvar senha em arquivo (Python 3.11+):

```powershell
$env:CLOUD_URL = 'https://SEU-SERVICO.onrender.com'
$env:CLOUD_OPERATOR_USERNAME = 'operador'
python tools/cloud_smoke.py
```

O script pede senha sem eco. Ele não valida a interface visual nem Socket.IO;
esses dois itens precisam do navegador. Não enviar senha/hash nas evidências.

## E. Manter dentro dos limites e diagnosticar

- A fonte gera eventos enquanto o processo está ativo: observar armazenamento no
  Supabase e quotas Render. Fechar o dashboard após uso; não deixar abas abertas
  continuamente sem necessidade. Pausas gratuitas podem exigir retomada manual.
- Para limpar eventos antigos, fechar clientes, salvar evidências e executar
  a poda já existente contra o banco cloud. Como Render Free não tem shell,
  usar uma execução local da imagem com DATABASE_URL fornecida por variável de
  ambiente, em terminal privado. Primeiro `prune --keep-days N` sem `--confirm`;
  escolher N conforme evidências que precisam ser preservadas. Só depois confirmar.
  Não usar SQL DELETE improvisado nem poda automática que prejudique replay.

Exemplo PowerShell para **consultar**, sem apagar, usando a imagem local:

```powershell
$entrada = Read-Host 'DATABASE_URL cloud (entrada oculta)' -AsSecureString
$dias = [int](Read-Host 'Quantos dias de eventos deseja preservar?')
try {
    $env:DATABASE_URL = [System.Net.NetworkCredential]::new('', $entrada).Password
    $env:OPERATOR_USERNAME = 'operador'
    docker run --rm -e DATABASE_URL -e OPERATOR_USERNAME netsentinel:local python -m netsentinel.api prune --keep-days $dias
} finally {
    Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:OPERATOR_USERNAME -ErrorAction SilentlyContinue
}
```

Se a quantidade estiver correta e as evidências já estiverem guardadas, repetir
esse bloco acrescentando `--confirm` ao comando `prune`. O modo sem essa flag
é apenas consulta. Não anexar a URL ou a senha ao registro do procedimento.

- Erro de banco: conferir projeto pausado, senha/percent-encoding, Session pooler
  5432 e TLS. Nunca imprimir DATABASE_URL inteira em logs públicos.
- Build indisponível/quota esgotada: aguardar renovação ou reduzir deploys; não
  mudar silenciosamente para plano pago. Memória insuficiente precisa ser medida
  no serviço real; não prometer que o plano Free já foi validado.
- Login perde sessão: HTTPS, hash completo, SECRET_KEY estável e mesmo domínio.
- Fonte parada ou WebSocket falhando: consultar status/logs; smoke verde não
  substitui inspeção do socket. Não aumentar workers/réplicas para tentar corrigir.
- Após congelamento acadêmico: RENDER_DEPLOY_ENABLED=false e Auto-Deploy Off.
  Para encerrar depois da feira, exportar evidências e revisar remoção dos recursos
  com o grupo; não apagar banco antes da avaliação.

## Fontes oficiais

- https://render.com/docs/free
- https://render.com/docs/blueprint-spec
- https://render.com/docs/deploys
- https://render.com/docs/websocket
- https://api-docs.render.com/reference/create-deploy
- https://api-docs.render.com/reference/retrieve-deploy
- https://supabase.com/pricing
- https://supabase.com/docs/guides/database/connecting-to-postgres
- https://supabase.com/docs/guides/api/securing-your-api
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
