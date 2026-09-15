# NetSentinel — captura, fuzzy, segurança e dashboard (0.6.0)

Entrega parcial do MVP: captura passiva Scapy, normalização, janela móvel, saída
JSON Lines e classificação fuzzy Mamdani com providers injetados.
Cenário ARP sem encaminhamento, agente de mitigação e executor local implementados
para validação nas VMs. Backend e dashboard visual implementados; deploy e ensaio nas VMs ainda pendentes.

**Para executar esta etapa, siga `lab/README.md` e os arquivos `*.example.json`.**

## Preparação

Python 3.11+ em Linux. Dependências declaradas em `pyproject.toml`.
Prepare dependências antes de isolar as VMs, ou transfira wheels offline.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

## Execução no Sensor

Configure primeiro o laboratório conforme `lab/README.md`. Substitua os três
valores abaixo pelos parâmetros do grupo; não há janela ou limite oficial definido.

```bash
sudo .venv/bin/python -m netsentinel.capture \
  --interface INTERFACE_INTERNA_DO_SENSOR \
  --window-seconds SEGUNDOS \
  --max-observations LIMITE \
  --isolated-lab
```

O indicador `--isolated-lab` é uma declaração de configuração, não uma verificação
capaz de inspecionar o VirtualBox. Isolamento é garantido na infraestrutura.
O processo captura somente na interface explícita. Ctrl+C/SIGTERM encerram a
captura e fecham o socket; há publicação final da janela.

## Contrato de saída

Cada linha é um snapshot JSON. `source=live` identifica esta fonte; a futura fonte
sintética de cloud deve ser identificada separadamente.

- `devices`: contagens por MAC de origem Ethernet, bytes, requests/replies ARP e
  primeiro/último timestamp **dentro da janela**, não reputação histórica.
- `arp_claims`: IP anunciado, MAC declarado no ARP, MAC de origem Ethernet e contagem.
  Requests e replies são separados nas métricas por dispositivo. Probes com IP de
  origem 0.0.0.0 não são tratados como afirmação de propriedade de endereço.
- `links`: pares direcionados de origem/destino Ethernet, incluindo broadcast e
  multicast; não equivalem a uma lista de dispositivos físicos descobertos.
- `incomplete`: houve descarte por capacidade que ainda afeta a janela atual.
  O motor fuzzy trata as entradas derivadas desse snapshot como ausentes.
- `evicted_total`: descartes acumulados pela capacidade da aplicação. **Não mede
  perdas no kernel, switch ou adaptador.**
- `unsupported_total` e `malformed_total`: observações não aproveitadas.

A janela é móvel, pelo instante monotônico de ingestão, com intervalo
(agora - duração, agora]. Timestamp do pacote é preservado para a timeline.
Aproximadamente a cada segundo é emitido um snapshot, inclusive em silêncio.
`observed_seconds` informa o tempo efetivamente observado, limitado à duração da
janela. `warming_up` indica que ainda não se completou a primeira janela. Não se deduz baseline ou
reputação do primeiro pacote. O volume conta bytes capturados por origem, sem
payload persistido e sem contabilizar overhead físico; não há deduplicação implícita.

O socket permanece aberto entre publicações, com modo promíscuo ativo e
`store=False`. O consumidor é síncrono e deve ser rápido; o módulo ainda não é
um coletor validado para alto volume. Snapshots agregados são recalculados em O(n).

Referência da API Scapy: https://scapy.readthedocs.io/en/latest/api/scapy.sendrecv.html

## Testes

```bash
PYTHONPATH=src .venv/bin/python tests/run_offline.py
```

**Resultado: 101 testes Python aprovados**, em Python 3.12, Scapy 2.7.0 e scikit-fuzzy 0.5.0.
A suíte inclui os 14 testes originais, pertinências/regras, autenticação, isolamento,
restauração, falhas parciais, contadores, timeout e aceitação
PCAP ponta a ponta do Atacante novo sem baseline, com e sem conflito observado. O runner evita descoberta de
interfaces/rotas do host, mantendo Scapy real para construção, dissecção e leitura
PCAP. O socket é mockado nos testes de ciclo de vida. Nenhum pacote é transmitido.
Em um host que permita a descoberta de interfaces, também é possível executar:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Ainda pendente: validação ao vivo dos quatro nós no VirtualBox. Não há evidência
nesta entrega de detecção/mitigação funcional ou cumprimento completo do NEXUS.

## Próximo módulo

Validação do Docker/Compose entregue e deploy/CD, além da validação nas VMs. Backend e dashboard já estão disponíveis; consulte `docs/backend.md` e `docs/dashboard.md`. O módulo de segurança desta versão
implementa `VictimAgentMitigationStrategy`, agente HTTP na Vítima, regras nftables,
ARP permanente e restauração. Testes offline não substituem a validação dessas
ações no kernel e no VirtualBox.

A VM Sensor terá duas interfaces: Internal Network para captura/agente e
Host-only para o dashboard no navegador do notebook, sem encaminhamento.
A aplicação cloud permanecerá separada e usará dados sintéticos.


## Motor fuzzy

`FuzzyRiskStrategy` implementa o contrato `ClassificationStrategy`. Recebe
`ReputationProvider` e `BaselineProvider` no construtor; não importa Repository,
Scapy ou Flask. Os providers fixos estão somente nos testes. Não aprende confiança
nem baseline do tráfego corrente. O chamador pode passar cada snapshot publicado
pela captura ao método `classify`.

```python
from netsentinel.analysis.fuzzy import FuzzyRiskStrategy

strategy = FuzzyRiskStrategy(reputation_provider, baseline_provider)
results = strategy.classify(snapshot)
# results[mac]: RiskResult com score, classificação, inputs, pertinências e regras.
```

O exemplo pressupõe providers fornecidos pelo chamador e um snapshot do
CaptureService; não é uma aplicação completa. Para serializar um resultado, use
`dataclasses.asdict(result)`. O snapshot precisa conter `observed_seconds` e
`warming_up`, adicionados nesta versão. Capturas JSON antigas devem ser regeneradas;
não estimamos a duração pelo intervalo entre o primeiro e o último pacote.

Entradas experimentais aprovadas:

| Entrada | Medida | Pertinência baixo/alto |
| --- | --- | --- |
| Conflito | Maior `1 - 1/n` entre os IPs reivindicados pela origem; n = MACs declarados distintos por IP | Linear 0–1 |
| Frequência | (ARP requests + replies) / observed_seconds | Linear 0–5/s, saturada acima |
| Reputação | known / new do provider | Categórica, 0 ou 1 |
| Desvio | abs(bytes/observed_seconds - baseline) / baseline | Linear 0–1, saturada acima |

O baseline deve usar **bytes capturados/s por MAC de origem**, não bits/s, soma
TX+RX ou taxa nominal da interface. MAC conhecido não é sinônimo de benigno.
Conflito sinaliza risco entre envolvidos; não atribui autoria do ataque.

| Regra | Antecedente | Consequente |
| --- | --- | --- |
| R1 | Conflito alto | Alto |
| R2 | Conflito baixo E (frequência alta OU desvio alto) E novo | Alto |
| R3 | Conflito baixo E (frequência alta OU desvio alto) E conhecido | Médio |
| R4 | Conflito baixo E frequência baixa E desvio baixo E novo | Médio |
| R5 | Conflito baixo E frequência baixa E desvio baixo E conhecido | Baixo |

Mamdani: AND mínimo, OR máximo, implicação mínimo, agregação máximo, centroide.
Primitivas reais de scikit-fuzzy: interpolação de pertinência, `trapmf`, `trimf`
e `defuzz`. Usamos a API de baixo nível para representar ausência de uma entrada
com pertinências todas zero, sem inventar um escalar para ControlSystemSimulation.
Referência: https://scikit-fuzzy.readthedocs.io/en/latest/api/skfuzzy.html

Saída 0–100: baixo trapézio [0,0,20,40], médio triângulo [30,50,70], alto trapézio
[60,80,100,100]. Classificação feita antes de arredondar: abaixo de 35 confiável;
35 até abaixo de 65 desconhecido; 65 ou mais suspeito. Isso é um score experimental,
não uma probabilidade calibrada. Parâmetros estão em `membership.py` e `engine.py`.

### Ausência de dados é tratada na inferência

- Baseline ausente, não positivo ou não finito: desvio `None`, graus baixo=alto=0.
- Reputação UNKNOWN/None: conhecido=novo=0. UNKNOWN não equivale a NEW.
- Captura incompleta ou em aquecimento: conflito, frequência e desvio indisponíveis.
  Preserva-se a política de qualidade aprovada; a inferência continua executada.
- Sem duração válida: frequência e desvio indisponíveis.
- Somente **todas as cinco forças iguais a zero** produz `score=None`,
  `classification=None` e `reason=no_rule_activated`.
- `inputs.missing_reasons` registra as lacunas mesmo quando há score. O resultado
  não é descartado só porque falta baseline ou reputação.

Exemplo central: novo, sem baseline, conflito=0 e frequência>=5/s ativa R2=1 e
classifica suspeito. Com conflito=0.5, R1 permanece ativa mesmo sem reputação.
Sem desvio disponível, R4/R5 não podem declarar baixo risco por ausência de prova.
Não há GA nem fallback manual de score no motor. O executor de segurança pode
acionar a mitigação quando há score >=65 E alegação falsa sobre o Gateway,
originada no Atacante configurado; essa decisão fica fora do motor fuzzy.

### Fixtures de aceitação

`tests/fixtures/demo_gateway_claim.pcap` e `demo_no_gateway_claim.pcap` são
sintéticos, com timestamps e endereços fixos. O gerador está em
`tests/fixtures/demo.py`; a suíte confere reprodução byte a byte. Os PCAPs são
lidos pelo Scapy real e entregues ao CaptureService com relógio injetado. Após a
janela amadurecer, o snapshot entra no motor com reputação NEW e baseline ausente.

A captura inclui 10 anúncios/s do Atacante. Na janela de 10 s observada no instante
12 s, há 99 anúncios (o limite esquerdo é aberto), resultando em 9,9/s. Um arquivo
inclui alegação do Gateway na mesma janela; o outro não. Ambos devem gerar score
>=65 para o Atacante. Nenhum pacote é transmitido pelos testes.

Essa aceitação não demonstra ping real caindo/voltando nem firewall funcionando.
Nas VMs ainda é necessário verificar se há alegação legítima na janela, se a
frequência real atinge 5/s, a visibilidade unicast do Sensor e o efeito da defesa.


Resultados desta execução de aceitação (Atacante NEW, sem baseline):

| Fixture | Conflito | Frequência | Regras ativas | Score | Classe |
| --- | --- | --- | --- | --- | --- |
| demo_gateway_claim.pcap | 0,5 | 9,9/s | R1=0,5; R2=0,5 | 82,38 | suspeito |
| demo_no_gateway_claim.pcap | 0 | 9,9/s | R2=1 | 84,44 | suspeito |

A diferença decorre dos recortes do consequente alto pelo grau de ativação;
esses scores não medem confiança estatística nem identificam autoria de ataque.


## Segurança nesta versão

- `security/attack.py`: envio ARP limitado ao Atacante/Vítima/Gateway configurados,
  forwarding obrigatoriamente desativado, limite de taxa e duração.
- `security/agent/`: Flask, ações fixas autenticadas, nftables netdev/ingress,
  associação ARP estática, journal e restauração local conservadora.
- `security/strategy.py`: cliente com IP de origem Internal Network do Sensor,
  timeout, sem proxies/redirects, repetição idempotente no agente.
- `security/demo.py`: captura com janela de 8 s, fuzzy e chamada da Strategy.
- `security/evidence.py`: deltas de tráfego visto/descartado/pós-filtro no mesmo
  run_id, com ARP correto; não considera silêncio ou recuperação de ping suficientes.
- `deploy/netsentinel-agent.service`: usuário dedicado e CAP_NET_ADMIN.

A aceitação integrada percorre PCAP sintético, Scapy, captura de 8 s, fuzzy,
Strategy e Flask. Somente o kernel e o transporte HTTP são substituídos nesse
ensaio; não houve envio real de ataque, filtro nft aplicado ou ping de VMs aqui.
No teste de transmissão limitada, o sender é um mock e o relógio é simulado.

A sequência do laboratório prepara o agente antes do ataque e inicia o executor
após a perda de ping ficar visível, para que uma resposta automática rápida não
oculte o efeito do envenenamento. A versão 0.5.0 reutiliza esses componentes no backend que serve o dashboard;
o executor CLI desta seção continua disponível para os ensaios anteriores.


## Integração contínua

`.github/workflows/ci.yml` executa lint e testes a cada PR, push em main e disparo
manual. Instalação local equivalente: `python -m pip install -e '.[dev]'`; depois
`python -m ruff check .` e `PYTHONPATH=src python tests/run_offline.py`.
O Ruff 0.16.6 está fixado para reproduzir as mesmas regras. Veja CONTRIBUTING.md
para ativação do check obrigatório no GitHub. O workflow foi criado, mas a
execução remota e a proteção da branch ainda dependem do repositório publicado.
Esta é a etapa CI; o deploy/CD continua pendente.

A ADR 0004 define promoção manual e auditada NEW -> KNOWN.
O Repository de reputação/baseline e o backend foram implementados na versão 0.4.0;
o dashboard visual foi adicionado na versão 0.5.0.


## Backend persistido (0.4.0)

Instruções e contrato REST/Socket.IO em `docs/backend.md`. Implementados:
SQLAlchemy 2, migrações Alembic, promoção manual auditada, baseline congelado pela
mediana de cinco taxas bytes/8 s e sessão do operador com CSRF. Cookie Secure=False
no laboratório HTTP, explicitamente; Secure=True no cloud. HttpOnly e SameSite=Lax
em ambos. Os testes confirmam sessão HTTP e a conversão de unidades do baseline.

O backend reutiliza SecurityDemo e VictimAgentMitigationStrategy com Repository
real em lugar dos providers fixos do executor anterior. Os eventos são persistidos
antes da notificação Observer. O executor CLI antigo permanece para testes e
ensaios anteriores; para a nova operação, usar `python -m netsentinel.api serve`.


## Dashboard visual (0.5.0)

Após iniciar o backend, abra `http://<IP-Host-only-do-Sensor>:<PORT>/` no notebook.
A tela de login busca CSRF antes de enviar a credencial. O dashboard oferece
topologia vis.js Network, dispositivos/risco, reconhecimento manual, calibração,
eventos, auditoria e evidências do agente com contadores anteriores/atuais/deltas.
Dados sintéticos e origem de laboratório são identificados explicitamente.

JavaScript puro e Tailwind compilado; todos os assets são locais. O pacote já
inclui o resultado do build e as licenças. Para editar e verificar o frontend:

```bash
cd frontend
npm ci
npm test
npm run build
```

9 testes JavaScript aprovados, além dos 101 Python. CI inclui o job frontend.
Node só é necessário para testes/build antes do isolamento; não para usar a demo.
Não houve validação visual em navegador nesta entrega. Testes de contratos e de
assets via Flask não comprovam interação/canvas/WebSocket no navegador real.
Veja `docs/dashboard.md` para o escopo da validação e pendências.


## Docker Desktop e confirmação consecutiva (0.6.0)

`Dockerfile` multi-stage (frontend + instalação Python + runtime) e
`docker-compose.yml` com serviço `synthetic` e Postgres local. O roteiro completo
para PowerShell, geração de credenciais e acesso por `http://localhost:8080/`
está em **[docs/docker.md](docs/docker.md)**. O container executa Gunicorn Linux;
Windows não precisa de instalação nativa de Gunicorn ou nftables.

A ADR 0007 exige duas avaliações consecutivas qualificando para o mesmo MAC antes
da mitigação; uma avaliação que não qualifica reinicia a sequência. Não impõe
atraso fixo de 16 s. O ensaio de queda/recuperação do ping continua pendente.

Validação atual: 101 testes Python, 9 JS, Ruff e build do frontend aprovados.
Imagem Docker, Compose/Postgres real, smoke HTTP do container e browser Windows
**não foram executados neste ambiente**, que não dispõe de Docker. O novo job de
CI prepara essa verificação quando executado no GitHub. Cloud Run/CD permanece
pendente; um Dockerfile não comprova deploy em nuvem concluído.
