# Docker Desktop no Windows — ambiente sintético 0.6.0

Esta execução usa containers Linux no Docker Desktop. Python, Gunicorn e build
do frontend ficam dentro da imagem; não é necessário instalá-los no Windows.
O serviço `synthetic` corresponde ao ambiente cloud/synthetic pedido: APP_MODE=cloud,
fonte artificial, Postgres em outro container e nenhum agente/captura real.
O nome do serviço é `synthetic` porque nomes de serviços Compose não usam `/`.

A imagem tem três estágios: build Node/Tailwind com `npm ci` e testes JS,
instalação Python e runtime Python sem Node/node_modules. O backend roda como
usuário sem root, com um worker Gunicorn e oito threads. O Compose remove todas
as capabilities do app; não requer nftables, NET_ADMIN, NET_RAW, modo privilegiado
ou rede host. A imagem inclui `ip` para o preflight do código do Sensor, mas o
modo sintético não o chama. O nftables permanece no agente da Vítima.

## Primeira execução no PowerShell

1. Iniciar Docker Desktop com **containers Linux**. Conferir `docker version` e
   `docker compose version`. Abrir o PowerShell na raiz extraída `netsentinel`
   (diretório que contém Dockerfile e docker-compose.yml).
2. Construir a imagem antes de gerar a configuração:

```powershell
docker build -t netsentinel:local .
Copy-Item .env.docker.example .env.docker
```

3. Gerar dois valores aleatórios e copiar cada um para seu campo em `.env.docker`:

```powershell
docker run --rm netsentinel:local python -c "import secrets; print('SYNTHETIC_POSTGRES_PASSWORD=' + secrets.token_hex(32)); print('SYNTHETIC_SECRET_KEY=' + secrets.token_hex(32))"
```

Usar a senha hexadecimal gerada para Postgres, evitando caracteres que precisariam
ser codificados na DATABASE_URL. Esses valores não são a senha de login da tela.

4. Gerar o hash da senha desejada para o operador, digitando a senha sem eco:

```powershell
docker run --rm -it netsentinel:local python -c "from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass('Senha do operador: ')))"
```

Copiar o hash inteiro para `SYNTHETIC_OPERATOR_PASSWORD_HASH` em `.env.docker`,
**mantendo as aspas simples** do exemplo. Isso preserva os `$` do hash.
O login é `SYNTHETIC_OPERATOR_USERNAME` (por padrão, `operador`) com a senha que
você digitou, não com o hash. Não há senha padrão. O Compose usa apenas as variáveis
SYNTHETIC_* explícitas; não importar LAB_CONFIG/token ou configuração das VMs.

5. Validar sem imprimir segredos e subir:

```powershell
docker compose --env-file .env.docker config --quiet
docker compose --env-file .env.docker up --build --wait --wait-timeout 180
docker compose --env-file .env.docker ps
```

O Postgres precisa ficar saudável antes de iniciar o app. O entrypoint executa
`python -m netsentinel.api migrate`; falha de migração impede iniciar Gunicorn.
Não é preciso executar migrate manualmente no Windows. Não há bootstrap automático:
dispositivos artificiais podem ser reconhecidos explicitamente no dashboard.

6. Abrir **http://localhost:8080/** e fazer login. O Compose publica somente
   `127.0.0.1:8080`, sem expor a porta do banco no notebook. Usar o hostname
   **localhost**, não o IP de rede do notebook, o IP das VMs nem Host-only.

## Sessão local e dados exibidos

SESSION_COOKIE_SECURE continua **True** no modo cloud; HttpOnly, SameSite=Lax e
CSRF permanecem ativos. O acesso HTTP local depende da exceção dos navegadores
para cookies Secure em **localhost**, documentada no
[MDN — Set-Cookie/Secure](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie#secure).
Não foi acrescentada uma flag que desabilita Secure na nuvem. No laboratório
Host-only real permanece a exceção Secure=False já aprovada para APP_MODE=lab.
Se o navegador não preservar a sessão em localhost, verificar cookies/políticas
nesse navegador; acesso por outro hostname/IP em HTTP não é o fluxo suportado.
Publicação externa/Cloud Run continua exigindo HTTPS.

O dashboard identificará **NUVEM · DADOS SINTÉTICOS**, porque usa a mesma fonte e
modo do deploy cloud; neste Compose, tudo está rodando localmente no notebook.
A captura artificial aquece em 8 s e começa a simular o ataque após cerca de 60 s
da inicialização da fonte. Pela ADR 0007, a defesa espera duas avaliações
consecutivas qualificantes. ARP e contadores exibidos nessa execução são simulados;
não existe ping real interrompido, envenenamento de uma VM ou prova de nftables.

## Parar, retomar e atualizar

```powershell
docker compose --env-file .env.docker logs --tail 100 synthetic
docker compose --env-file .env.docker down
docker compose --env-file .env.docker up --build --wait --wait-timeout 180
```

O volume `synthetic_postgres` preserva banco, reputação, baseline e eventos entre
execuções. Não usar `down --volumes` se quiser manter esses dados. Alterar a senha
no `.env.docker` não altera automaticamente a senha de um Postgres já inicializado;
manter a senha original do volume enquanto ele for reutilizado.
Reiniciar o app reinicia o relógio do cenário artificial, não limpa o histórico.

## Migração no Postgres e CI

Após o Compose subir, consultar a revisão aplicada:

```powershell
docker compose --env-file .env.docker exec -T postgres psql -U netsentinel -d netsentinel -v ON_ERROR_STOP=1 -c "SELECT version_num FROM alembic_version;"
```

A existência da revisão e endpoints operacionais registra uma verificação inicial
contra Postgres real local; não substitui o teste no Postgres gerenciado escolhido
para produção. Guardar a saída da revisão, `ps`, logs sem segredos e evidências do
acesso autenticado quando o grupo executar.

O CI ganhou job de container: gera credenciais efêmeras, constrói a imagem, sobe
Compose/Postgres, verifica HTTP e consulta alembic_version. Seu smoke HTTP usa
cookie explícito para testar API/CSRF; não valida políticas de cookies no browser.
O encerramento desse job remove somente o volume efêmero usado no runner de CI.

## Verificação feita nesta entrega

101 testes Python e 9 testes JS passaram, além de Ruff e build do frontend.
YAML foi lido e a sintaxe do script shell conferida. **Docker/Compose e socket do
daemon não estão disponíveis neste ambiente:** não foi executado docker build,
Compose, o smoke de container, Postgres real ou navegador Windows nesta entrega.
O job foi escrito, mas ainda depende de execução no GitHub. Não registrar essas
etapas como aprovadas até rodarem no Docker Desktop ou no CI.

Dockerfile e Compose adiantam containerização, mas não equivalem a deploy em
nuvem concluído: Cloud Run, Postgres gerenciado e pipeline de publicação continuam
pendentes. O Compose sintético não é configuração de rede para o ataque real nas
VMs. Não conectar esse ambiente ao segmento isolado do laboratório.
