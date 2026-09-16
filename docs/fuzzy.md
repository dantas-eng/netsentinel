# Motor fuzzy

`FuzzyRiskStrategy` classifica o risco de cada dispositivo de um snapshot da
captura. Ele implementa o contrato `ClassificationStrategy` e recebe
`ReputationProvider` e `BaselineProvider` no construtor, sem importar Repository,
Scapy ou Flask. Não aprende confiança nem baseline a partir do tráfego corrente.

```python
from netsentinel.analysis.fuzzy import FuzzyRiskStrategy

strategy = FuzzyRiskStrategy(reputation_provider, baseline_provider)
results = strategy.classify(snapshot)
# results[mac]: RiskResult com score, classificação, inputs, pertinências e regras.
```

O exemplo pressupõe providers do chamador e um snapshot do `CaptureService`. Para
serializar um resultado, use `dataclasses.asdict(result)`. O snapshot precisa ter
`observed_seconds` e `warming_up`; capturas JSON antigas devem ser regeradas,
porque não estimamos a duração pelo intervalo entre o primeiro e o último pacote.

## Entradas

| Entrada | Medida | Pertinência baixo/alto |
| --- | --- | --- |
| Conflito | Maior `1 - 1/n` entre os IPs reivindicados pela origem; n = MACs declarados distintos por IP | Linear 0–1 |
| Frequência | (ARP requests + replies) / `observed_seconds` | Linear 0–5/s, saturada acima |
| Reputação | known / new do provider | Categórica, 0 ou 1 |
| Desvio | `abs(bytes/observed_seconds - baseline) / baseline` | Linear 0–1, saturada acima |
| Razão de replies ARP | `arp_replies / (arp_requests + arp_replies)`; `None` se não houve ARP na janela | Rampa 0,5–1,0 (`RATIO_HIGH_FLOOR=0.5`); baixo é o complemento |

O baseline usa **bytes capturados/s por MAC de origem** — não bits/s, não soma
TX+RX, não taxa nominal da interface. MAC conhecido não é sinônimo de benigno, e
conflito sinaliza risco entre os envolvidos sem atribuir autoria do ataque.

O piso `RATIO_HIGH_FLOOR=0.5` é justificado em
[validation/fuzzy-metrics.md](validation/fuzzy-metrics.md).

## Regras

São cinco. `anomalous` é o máximo entre frequência alta, desvio alto e razão
alta. R4 e R5 exigem também razão baixa, então sem tráfego ARP a razão fica
`None` e essas duas regras não declaram risco baixo.

| Regra | Antecedente | Consequente |
| --- | --- | --- |
| R1 | Conflito alto | Alto |
| R2 | Conflito baixo E `anomalous` E novo | Alto |
| R3 | Conflito baixo E `anomalous` E conhecido | Médio |
| R4 | Conflito baixo E frequência baixa E desvio baixo E razão baixa E novo | Médio |
| R5 | Conflito baixo E frequência baixa E desvio baixo E razão baixa E conhecido | Baixo |

## Inferência

Mamdani: AND mínimo, OR máximo, implicação mínimo, agregação máximo,
defuzzificação por centroide. Usamos primitivas de baixo nível do scikit-fuzzy
(`trapmf`, `trimf`, interpolação de pertinência e `defuzz`) porque isso permite
representar uma entrada ausente com todas as pertinências em zero, em vez de
inventar um escalar para `ControlSystemSimulation`.

Saída de 0 a 100: baixo é o trapézio [0,0,20,40], médio o triângulo [30,50,70],
alto o trapézio [60,80,100,100]. A classificação acontece antes do
arredondamento: abaixo de 35 é confiável, de 35 a menos de 65 é desconhecido, 65
ou mais é suspeito. É um score experimental, não uma probabilidade calibrada. Os
parâmetros estão em `membership.py` e `engine.py`.

Referência da API:
<https://scikit-fuzzy.readthedocs.io/en/latest/api/skfuzzy.html>

## Ausência de dados

- Baseline ausente, não positivo ou não finito: desvio `None`, graus baixo e alto em zero.
- Reputação UNKNOWN ou None: conhecido e novo em zero. UNKNOWN não equivale a NEW.
- Captura incompleta ou em aquecimento: conflito, frequência e desvio ficam indisponíveis.
- Sem duração válida: frequência e desvio ficam indisponíveis.
- Só quando **as cinco forças são zero** o resultado é `score=None`, `classification=None` e `reason=no_rule_activated`.
- `inputs.missing_reasons` registra as lacunas mesmo quando há score. O resultado não é descartado só porque falta baseline ou reputação.

Exemplo central: dispositivo novo, sem baseline, conflito 0 e frequência de 5/s
ou mais ativa R2=1 e classifica como suspeito. Com conflito 0,5, R1 continua
ativa mesmo sem reputação. Sem desvio disponível, R4 e R5 não podem declarar
risco baixo por falta de prova.

A decisão de mitigar fica fora do motor. O executor aciona a defesa quando há
score >= 65 e alegação falsa sobre um IP de `trusted_bindings()`, e só o MAC
autorizado por `LabConfig.require_attacker` segue a sequência da
[ADR 0007](decisions/0007-duas-avaliacoes-antes-da-mitigacao.md); os demais
geram `threat_unmitigable`. Ver
[ADR 0008](decisions/0008-deteccao-ampla-mitigacao-restrita.md).

## Fixtures de aceitação

`tests/fixtures/demo_gateway_claim.pcap` e `demo_no_gateway_claim.pcap` são
sintéticos, com timestamps e endereços fixos. O gerador está em
`tests/fixtures/demo.py` e a suíte confere reprodução byte a byte. Os PCAPs são
lidos pelo Scapy real e entregues ao `CaptureService` com relógio injetado.

A captura inclui 10 anúncios/s do Atacante. Na janela de 10 s observada no
instante 12 s há 99 anúncios (o limite esquerdo é aberto), ou seja 9,9/s. Um dos
arquivos inclui alegação do Gateway na mesma janela, o outro não. Nenhum pacote é
transmitido pelos testes.

| Fixture | Conflito | Frequência | Regras ativas | Score | Classe |
| --- | --- | --- | --- | --- | --- |
| demo_gateway_claim.pcap | 0,5 | 9,9/s | R1=0,5; R2=0,5 | 82,38 | suspeito |
| demo_no_gateway_claim.pcap | 0 | 9,9/s | R2=1 | 84,44 | suspeito |

A diferença vem dos recortes do consequente alto pelo grau de ativação. Esses
scores não medem confiança estatística nem identificam autoria de ataque, e a
aceitação não demonstra ping caindo e voltando nem firewall funcionando. Nas VMs
ainda é preciso verificar se existe alegação legítima na janela, se a frequência
real chega a 5/s, a visibilidade unicast do Sensor e o efeito da defesa.
