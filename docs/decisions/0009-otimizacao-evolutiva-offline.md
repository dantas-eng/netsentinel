# ADR 0009 — Otimização evolutiva offline do classificador fuzzy

- Data: 19/09/2026.
- Status: implementação autorizada pelo grupo; aceite da trilha própria pendente do professor.
- Escopo: extensão da disciplina Computational Intelligence & Algorithm Optimization.

## Contexto

O MVP usa Mamdani para classificação, suficiente para a interpretação aprovada do roteiro
NEXUS, mas a disciplina adicional exige otimização real, baseline obrigatório e múltiplas
execuções com média e desvio-padrão. Um projeto paralelo duplicaria esforço e perderia
integração com o problema de segurança já desenvolvido.

## Decisão

Adicionar `netsentinel.optimization` como extensão offline. `FuzzyRiskStrategy` permanece
inalterado e é o baseline manual obrigatório. `ParameterizedFuzzyRiskStrategy` implementa
estruturalmente `ClassificationStrategy`, com os mesmos providers injetados e reutilização
direta de `analysis/fuzzy/rules.py:evaluate`. Não substituir a estratégia usada pela API,
SecurityDemo ou serviços. Nenhum resultado experimental ativa defesa real.

Para cada feature presente x e saturação s: alto = min(x/s, 1), baixo = 1 − alto.
Para feature ausente, ambas as pertinências são zero. Reputação ausente também tem zero
em todos os conjuntos. A abstenção surge somente quando todas as regras têm força zero.
Mantêm-se AND=min, OR=max, agregação=max e centroide. Consequentes: trapezoidal baixo
[0,0,20,40], triangular médio [30,50,70], trapezoidal alto [60,80,100,100].
A integração vetorizada usa segmentos lineares e seus cruzamentos; testes verificam
equivalência com a implementação manual, sem alterar esta última.

| Gene | Faixa inclusiva | Manual |
|---|---:|---:|
| Saturação de conflito | 0,1–1,0 | 1,0 |
| Saturação de frequência ARP | 1–20 anúncios/s | 5 |
| Saturação de desvio relativo | 0,25–4 | 1 |
| Limiar suspeito | 50–85 | 65 |

Conflito = 1 − 1/n, portanto é menor que 1 para n finito. Saturação acima de 1
nunca seria alcançada, embora ainda produzisse pertinências distintas. O limite s=1
preserva a parametrização manual como ponto admissível do espaço de busca; não significa
que uma entrada real alcance pertinência 1 nesse caso. O limiar inferior permanece 35
na busca. A classe aceita configurá-lo, mas ele não influencia a decisão binária de ataque.

## Dataset e protocolo

600 cenários sintéticos independentes de uma janela completa de 8 s: 420 benignos e
180 ataques. PCAPs construídos em memória, serializados e relidos; passam pelo
CaptureService e FeatureExtractor reais. Nenhum pacote é transmitido. Identificadores,
contexto, rótulos, hashes e splits acompanham os dados. Rótulo vem da intenção e autorização
do cenário gerador, nunca da saída do fuzzy.

Split fixo estratificado por família: 360 treino, 120 validação, 120 teste, sempre 70/30.
Cada cenário fica integralmente em um único split; não há janelas sobrepostas. Gerador
com semente 20260919. Providers simulam reputação e histórico anteriores à janela;
nenhum repositório da aplicação é modificado. Há benignos novos, conhecidos, sem informação,
picos legítimos e migração autorizada de IP ambígua. Ataques variam intensidade e presença
de reivindicação do gateway. A sobreposição é deliberada: as features não observam autorização.

CIC-IDS2017 e UNSW-NB15 fundamentam a necessidade de tráfego benigno variado e ataques
rotulados. Não são fonte dos PCAPs, dos valores das features, de distribuições ajustadas
ou de medições desta extensão. Não se alega equivalência com seus esquemas de features.
Detalhes, referências oficiais e limitações estão em `research/README.md`.

## Algoritmos aprovados

DEAP 1.4.4; 20 execuções de cada método, sementes 0–19; população 40, 40 gerações
(além da avaliação inicial). Inicialização uniforme nas faixas. Cruzamento SBX limitado,
probabilidade 0,9 por par, eta=20. Mutação polinomial limitada, probabilidade 0,2 por
indivíduo, probabilidade 1/4 por gene, eta=20.

- AG: maximizar F1 no treino; torneio de tamanho 3; dois elites; 38 descendentes.
  Hall of Fame dos dois melhores candidatos de treino; escolha entre eles por validação.
- NSGA-II: maximizar recall e minimizar FPR no treino. Torneio de dominância/crowding
  (`selTournamentDCD`) para pais; seleção ambiental `selNSGA2` sobre pais + 40 descendentes.
  Arquivo Pareto guarda soluções não dominadas visitadas, inclusive genótipos distintos
  com os mesmos objetivos. Escolha de um representante por execução nesse arquivo.
- Seleção final: maior F1 na validação, depois menor FPR; empate completo resolvido
  lexicograficamente pelos genes, para reprodução. O teste não entra no otimizador.
- Mesmo dataset e split para ambos. Cache apenas de avaliação de genótipos idênticos,
  sem arredondamento e sem alterar o número de gerações.

## Relato e consequências

Precisão, recall, F1 e FPR no teste reservado, matrizes de confusão, abstenções separadas.
Abstenção conta como não detecção; denominadores não excluem exemplos difíceis.
Divisões sem denominador retornam zero. Média e desvio-padrão amostral (ddof=1) entre
as 20 sementes. Baseline determinístico relatado uma vez. Não se interpreta esse desvio
como variabilidade entre redes reais ou intervalos de confiança de generalização.

A frente mostrada é empírica, não prova de ótimo global. O gráfico identifica explicitamente
objetivos de treino; pontos de teste dos representantes aparecem separados. Não há escolha
de modelo baseada no teste. Empate, regressão ou frente com um único ponto são resultados
válidos; não ajustar dados ou hiperparâmetros após observar o teste para fabricar melhoria.

Mantêm-se pendentes: aceite docente da trilha, validação em tráfego real e ensaio das VMs.
A extensão não conclui deploy em nuvem nem ensaio de mitigação. Qualquer adoção operacional
exigiria decisão separada, inclusive compatibilização com o limiar 65 da defesa atual.

## Proveniência e atualização

Este documento era ADR 0008 no ramo de otimização derivado da 0.6.0. Renumerado
para 0009 porque a base 0.7.0 já usa 0008 para detecção ampla/mitigação restrita.
O protocolo original acima é histórico. A adaptação à quinta entrada fixa e a
comparação atual são descritas na ADR 0010.
