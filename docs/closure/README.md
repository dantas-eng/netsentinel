# Guia de execução — fechar o NetSentinel

Atualizado em 28/09/2026. Base: main 692a414. Trilha própria aprovada pelo
professor conforme e-mail fornecido pelo grupo. Documentos NEXUS/Regulamento
prevalecem; este guia não atesta ensaios ainda não feitos.

## Ordem de trabalho e responsáveis

| Etapa | Quem executa | Critério de saída |
|---|---|---|
| 1. Revisar e integrar esta preparação | Autor + revisor diferente | PR aprovado e três checks verdes |
| 2. Criar Supabase/Render e ativar CD | Responsável pelas contas | Deploy live do SHA aprovado e smoke HTTPS verde |
| 3. Validar banco gerenciado e browser | Grupo | Revisão Alembic, persistência, sessão e Socket.IO comprovados |
| 4. Ensaiar as quatro VMs | Frente de segurança + observador | Ping antes/durante/depois, filtro e ARP comprovados |
| 5. Consolidar evidências e congelar | Líder + revisão cruzada | Compliance atualizado com provas, versão/commit final |
| 6. Gravar pitch e estudar sabatina | Todos | Vídeo <=3 min e todos explicam o pipeline completo |

Etapas 2/3 e 4 podem ser feitas em paralelo por integrantes diferentes. A nuvem
usa dados sintéticos e nunca se conecta às VMs. Não desenvolver novas features
durante o fechamento; corrigir falhas concretas reveladas pelos ensaios.

## 1. Integrar a entrega por um PR real

Os branches antigos já foram integrados. Partir da main atual, não fundi-los de
novo. O pacote contém os arquivos completos e um patch relativo ao commit
692a414; preferir o patch para não sobrescrever trabalho novo.

No PowerShell, dentro do clone local (árvore limpa):

```powershell
git status --short
git switch main
git pull --ff-only
git switch -c chore/fechamento-deploy-gratuito
git apply --check "C:\CAMINHO\netsentinel-fechamento.patch"
git apply "C:\CAMINHO\netsentinel-fechamento.patch"
git diff --stat
```

Substituir CAMINHO pela pasta extraída. Se `--check` falhar, a main mudou; revisar
o conflito em vez de forçar cópia ou usar reset. O patch inclui novos arquivos.
Se `git status` mostrar trabalho local antes de começar, preservar esse trabalho.

Para testar no Windows com Python 3.12 e Node 22 disponíveis:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]" -r requirements-optimization.txt
.\.venv\Scripts\python tests/run_offline.py
.\.venv\Scripts\python -m unittest research.tests.test_optimization -v
.\.venv\Scripts\python -m ruff check .
Push-Location frontend
npm ci
npm test
npm run build
Pop-Location
git diff --exit-code -- src/netsentinel/api/static
```

Esses testes não precisam executar Gunicorn/nftables no Windows. Para explorar o
dashboard, seguir [Docker Desktop](../docker.md). Se pip de alguma dependência
não funcionar no host Windows, executar a suíte no runner Linux da CI; não
confundir instalação local com defeito do app sem ler o erro.

Revisar o diff e adicionar somente os arquivos pretendidos (nunca `.env`, tokens
ou configuração real do lab), fazer commit/push dessa branch e abrir PR para main.
Outro integrante revisa; então integrar com os três checks verdes. Nenhum push
ou merge remoto foi feito automaticamente nesta entrega.

## 2 e 3. Nuvem gratuita e Postgres

Seguir [cloud.md](cloud.md), na ordem: banco, serviço, CD, smoke, banco/browser,
controle de quotas. Credenciais ficam nas contas do grupo, não nesta conversa.

O CD começa desativado. O primeiro deploy de criação não fecha o requisito:
é necessário registrar uma publicação disparada pelo GitHub Actions depois dos
checks, junto da URL HTTPS e do commit efetivamente publicado.

## 4. Ensaio físico

Seguir [lab-validation.md](lab-validation.md), que complementa o roteiro de
[lab/README.md](../../lab/README.md) sem criar outro executor.

## 5. Evidências e congelamento

Preencher [evidence-template.md](evidence-template.md) com resultados reais.
O modelo começa PENDENTE de propósito. Guardar vídeos curtos/screenshots e saídas
sanitizadas, vinculados ao commit. Não substituir prova por checkbox marcado.

Atualizar docs/compliance.md somente depois das verificações. Preservar links de
PRs #3/#4 e da nova revisão: não é necessário criar colaboração artificial.
Guardar a aprovação docente em canal restrito do grupo; o repositório pode apenas
registrar a aprovação sem publicar e-mails pessoais.

Antes do congelamento, definir a nova versão semântica com o grupo e manter
pyproject/README/CHANGELOG coerentes. A tag v0.7.0 é anterior à otimização:
não movê-la para outro commit. Criar uma nova tag/release do commit final revisado.

Depois de congelar, colocar RENDER_DEPLOY_ENABLED=false; manter Render
Auto-Deploy Off e, se usar Blueprint, sua sincronização automática desativada.
Não modificar código/projeto após avaliação individual sem autorização expressa.

## 6. Pitch e sabatina

Roteiro e perguntas: [presentation.md](presentation.md). Ensaiar alternância de
papéis: quem fez frontend explica nftables; quem fez segurança explica NSGA-II;
quem fez pesquisa explica sessão/CSRF e persistência.

## Datas para planejar

O guia da disciplina prevê protótipo/modelo em 04/10, MVP1 até 01/11 e entrega
final em 21/11. O regulamento do integrador prevê avaliação individual entre
09 e 13/11, sem alteração posterior. Confirmar a data da turma e planejar
congelamento **antes dela**; se ainda desconhecida, trabalhar com 08/11 como
limite conservador. ExpoTech: 28/11. Não assumir janela de ajustes até a feira.

O grupo deve conferir também inscrição, nomes/RAs, equipe de 3–5 integrantes,
presença obrigatória e canal/prazo efetivo de envio do vídeo e documentos.
Esses atos acadêmicos não podem ser certificados pelo código ou por esta entrega.
