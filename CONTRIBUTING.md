# Como contribuir

Este guia descreve como o grupo trabalha no NetSentinel: branches, commits, pull
requests, verificações locais e o que olhar numa revisão. Ele vale para código,
documentação e pesquisa.

## Fluxo de trabalho

1. Atualize a `main` e crie uma branch a partir dela.
2. Faça commits pequenos e com mensagem descritiva.
3. Rode as verificações locais (seção abaixo).
4. Abra um pull request para a `main`.
5. Outro integrante revisa. O merge só acontece com aprovação e os checks verdes.

A `main` é protegida: não aceita push direto e exige os três checks do CI e uma
aprovação de alguém que não é o autor do PR.

### Nomes de branch

Use um prefixo que diga o tipo de mudança, seguido de uma descrição curta em
minúsculas com hífens:

| Prefixo | Uso | Exemplo |
| --- | --- | --- |
| `feat/` | Funcionalidade nova ou mudança de comportamento | `feat/classificacao-legitimos` |
| `fix/` | Correção de defeito | `fix/janela-incompleta` |
| `docs/` | Só documentação | `docs/readme-contributing` |
| `research/` | Experimentos e resultados de otimização | `research/corpus-v3` |
| `chore/` | Build, CI, deploy, dependências | `chore/fechamento-deploy-gratuito` |

### Mensagens de commit

O histórico segue o formato `tipo(escopo): resumo`, em português e no imperativo.
O escopo é opcional.

```
feat(fuzzy): conflito pela reputação e amostra mínima da razão ARP
fix(api): rejeitar paginação com limite zero
docs: ADR 0013 e documentação da classificação de legítimos
```

Use o corpo do commit para explicar o porquê quando ele não for óbvio pelo diff.

## Verificações locais

Rode na raiz do repositório antes de abrir o PR. São os mesmos comandos do CI.

```bash
python -m pip install -e '.[dev]'
python -m ruff check .
PYTHONPATH=src python tests/run_offline.py
```

Se a mudança tocar `src/netsentinel/optimization/` ou `research/`:

```bash
python -m pip install -r requirements-optimization.txt
python -m unittest research.tests.test_optimization
```

Se tocar o dashboard, em `frontend/`:

```bash
npm ci
npm test
npm run build
```

Depois do build, `git status` não pode mostrar diferença em
`src/netsentinel/api/static/` além do que você pretendia mudar. O CI confere isso.

Nenhuma verificação local usa sudo, VMs, token do agente ou nftables reais.

## Pull requests

A descrição do PR deve dizer:

- o objetivo e o comportamento que muda;
- como foi testado, com os comandos executados;
- limitações conhecidas e o que fica para depois.

Mantenha o PR focado num assunto. Mudanças de comportamento do classificador
precisam de uma ADR em `docs/decisions/` e da atualização de `docs/fuzzy.md`.
Mudanças que afetam evidências do roteiro NEXUS precisam refletir em
`docs/compliance.md`. Registre a mudança em `CHANGELOG.md`, na seção
"Não lançado".

## CI

O workflow `.github/workflows/ci.yml` roda em cada pull request, em push para a
`main` e sob demanda. São três jobs obrigatórios:

| Job | O que verifica |
| --- | --- |
| Lint e testes offline | Ruff, suíte offline, testes da otimização e harness de métricas fuzzy |
| Frontend offline | Testes JavaScript, build dos assets e diferença entre fontes e assets versionados |
| Container e Postgres sintéticos | Imagem Docker, smoke HTTP com sessão e revisão Alembic num Postgres efêmero |

O job de deploy no Render só roda na `main` e quando a variável
`RENDER_DEPLOY_ENABLED` está ativa; nos PRs ele aparece como ignorado.

Ruff está fixado no extra `dev` do `pyproject.toml`, com as regras E4, E7, E9 e F.
O CI não corrige nada automaticamente: problemas apontados devem ser resolvidos no
próprio PR.

## O que olhar numa revisão

Além de legibilidade e testes, confira os pontos em que este projeto costuma errar:

- **Captura:** origem Ethernet observada e MAC alegado no ARP nunca podem ser
  confundidos; limites da janela e encerramento do socket.
- **Classificador:** ausência de dado não é zero; nenhuma regra pode declarar risco
  baixo a partir de um valor inventado; os scores das fixtures de aceitação não
  mudam sem ADR.
- **Mitigação:** só o MAC autorizado é mitigado; a evidência exige contadores
  comparáveis; ping sozinho não comprova defesa.
- **Dashboard:** CSRF antes do login e rotação depois; conteúdo recebido inserido
  como texto, nunca como HTML; reconexão sem pular eventos; reputação separada de
  risco.
- **Pesquisa:** o conjunto de teste não escolhe parâmetros; números reportados
  como saíram; resultados que deixam de valer vão para
  `research/historical-invalid/` com a explicação.

## Segurança e dados sensíveis

Nunca versione `.env`, `.env.docker`, tokens do agente, hashes de senha reais ou a
configuração real do laboratório. Os arquivos `*.example*` existem para isso. O
código de ataque só pode ser executado nas VMs isoladas do laboratório.

## Versões

O projeto usa versionamento semântico. A versão está em `pyproject.toml` e
`frontend/package.json`. Uma nova tag só é criada sobre um commit revisado da
`main`, junto com a entrada correspondente no `CHANGELOG.md`. Tags existentes não
são movidas.
