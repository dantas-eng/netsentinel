# Contribuição

Use branches `feature/nome`, commits descritivos e PR para `main`. Todo merge
precisa de revisão de outro integrante. A proteção de branch deve ser configurada
no GitHub quando o repositório for criado; este arquivo não a ativa.

Execute os testes descritos no README antes do PR. Na descrição, registre objetivo,
comportamento alterado, testes executados e limitações. Revise especialmente:
origem Ethernet versus alegação ARP, limites da janela, qualidade das métricas e
encerramento do socket. Preserve o histórico real das revisões.

Versão inicial do módulo: 0.1.0. Ainda não há tag ou PR publicado por esta entrega.

## CI em cada pull request

O workflow `.github/workflows/ci.yml` executa Ruff e a suíte offline em Python 3.12.
Também roda em push para main e pode ser disparado manualmente. Sem filtro de
caminhos: PRs de documentação também recebem o check. Os testes rodam mesmo se
Ruff falhar, desde que a instalação das dependências tenha funcionado.

Na raiz do repositório, reproduza os mesmos comandos:

```bash
python -m pip install -e '.[dev]'
python -m ruff check .
PYTHONPATH=src python tests/run_offline.py
```

Ruff está fixado na versão 0.16.6 no extra dev. As regras habilitadas são E4, E7,
E9 e F. Não há correção automática no CI; os problemas devem ser corrigidos no PR.
Não se usa sudo, VMs, token do agente ou nftables nos testes. A instalação de
pacotes requer acesso ao índice; o runner de testes é offline em relação à rede
monitorada. O workflow usa pull_request, não pull_request_target, e permissions
contents: read; não publica nem faz deploy.

O arquivo precisa estar em `.github/workflows/` na raiz do repositório GitHub,
junto a pyproject.toml e tests/. Ao copiar o ZIP, não adicionar uma pasta
netsentinel extra acima dessa raiz. Depois da primeira execução no GitHub,
configurar o check `Lint e testes offline` como obrigatório na proteção de main,
junto à aprovação de outro integrante. O YAML não configura proteção de branch.
Esta entrega valida os comandos localmente; ainda não há execução remota comprovada.


## Frontend

JavaScript puro em `src/netsentinel/api/static/`, template Flask em
`src/netsentinel/api/templates/` e fonte Tailwind em `frontend/styles.css`.
Antes do PR, em `frontend/`: `npm ci`, `npm test`, `npm run build`.
Versionar o lockfile, os assets compilados e as licenças. O job frontend do CI
confere os testes, a compilação e diferenças entre assets e fontes.

Na revisão, verificar CSRF pré-login e rotação pós-login, nenhum dado renderizado
como HTML não confiável, recuperação REST sem pular IDs recebidos por Socket.IO,
separação reputação/risco e ausência de conclusões sobre ping sem medição.


## Container

O job `container` usa Compose com Postgres efêmero e credenciais geradas no runner,
executa `tests/container_smoke.py` por HTTP e consulta a revisão Alembic. Esse
smoke não integra `tests/run_offline.py`: exige Docker/serviço real e não valida
cookies no navegador. Nunca versionar `.env.docker`. O script de início usa LF
para funcionar em containers Linux mesmo com checkout no Windows.
