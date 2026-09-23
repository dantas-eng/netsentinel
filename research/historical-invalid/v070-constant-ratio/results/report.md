# Comparação experimental — dados exclusivamente sintéticos

Baseline: fuzzy manual 0.7.0. Ratio ARP usa rampa fixa 0,5–1,0; quatro genes são otimizados. O teste reservado não participa da busca nem da escolha de representantes.

Limitação do corpus preservado: todos os 600 PCAPs contêm somente replies ARP, logo ratio=1 inclusive nos benignos. Não se avalia discriminação por mistura requests/replies. Resultados 0.6.0 ficam separados em historical-v060/ e não são o baseline desta tabela.

| Método | Precisão | Recall | F1 | FPR | Abstenções |
|---|---:|---:|---:|---:|---:|
| Manual (determinístico) | 0.3766 | 0.8056 | 0.5133 | 0.5714 | 14.0000 |
| ga (20 sementes) | 0.3766 ± 0.0000 | 0.8056 ± 0.0000 | 0.5133 ± 0.0000 | 0.5714 ± 0.0000 | 14.0000 ± 0.0000 |
| nsga2 (20 sementes) | 0.3766 ± 0.0000 | 0.8056 ± 0.0000 | 0.5133 ± 0.0000 | 0.5714 ± 0.0000 | 14.0000 ± 0.0000 |

Valores: média ± desvio-padrão amostral (ddof=1). O baseline é uma única execução determinística; a variação dos métodos mede somente aleatoriedade da busca neste split, não incerteza de generalização.

Neste split, pelo menos um método não superou o F1 do manual.

A frente agrupada contém 4 pontos objetivos distintos. As ligações no gráfico são guias visuais, não soluções intermediárias garantidas.

O painel de teste plota as 20 execuções individuais de cada método, com transparência alpha=0,14, sem jitter. Círculos azuis representam AG e quadrados laranja vazados representam NSGA-II. Pontos coincidentes se sobrepõem; os rótulos informam quantas sementes ocupam cada ponto. O painel não mostra médias nem barras de erro; média e desvio-padrão permanecem na tabela.

![Frente e teste](pareto.png)

Não há garantia de superioridade sobre o manual. Sobreposição entre famílias benignas e ataques limita a separação pelas quatro features. Resultados não constituem validação em tráfego real ou nas VMs. Nenhuma configuração é promovida automaticamente à aplicação.

Tempo total de otimização/avaliação: 294.0 s.
Dados, hashes de PCAP, sementes, parâmetros individuais, versões e arquivos de treino completos estão em dataset/dataset.json e results.json.

## Genótipos e decisões observadas

Verificação dos genes crus em `results.json`: 20 genótipos distintos em 20 execuções do NSGA-II. A saturação de frequência varia de 1.28501400 a 17.64674531 anúncios/s (aproximadamente 1.29–17.65).

| Método | Execuções | TP | FP | FN | TN | Sementes |
|---|---:|---:|---:|---:|---:|---|
| GA | 20/20 | 29 | 48 | 7 | 36 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 |
| NSGA2 | 20/20 | 29 | 48 | 7 | 36 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 |

A comparação exemplo a exemplo encontrou 1 vetor(es) distinto(s) de decisões binárias nas execuções do NSGA-II.

Os 20 genótipos comprovadamente distintos do NSGA-II convergem para a mesma matriz de confusão no conjunto de teste. Isso é evidência de um platô do comportamento de decisão avaliado nesse conjunto, não de convergência genética. Não demonstra que os scores contínuos sejam iguais ou que as decisões coincidam em dados fora do teste.

O AG ocupa 1 grupo(s) de matriz de confusão; o desvio-padrão amostral de F1 é 0.00000000.
