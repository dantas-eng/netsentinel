# Pitch e preparação individual

Vídeo de até 3 minutos conforme regulamento. Este roteiro é rascunho; trechos
de demonstração só devem usar o ensaio real depois de validado. Preparar uma
versão de 2min40s a 2min50s para manter margem, sem acelerar a fala.

## Roteiro sugerido

| Tempo | Fala/ação |
|---|---|
| 0:00–0:20 | Problema: ARP não autentica a associação IP/MAC; uma alegação falsa pode desviar e interromper tráfego local. Apresentar o NetSentinel. |
| 0:20–0:45 | Mostrar as quatro VMs isoladas e o dashboard. Explicar Sensor passivo, Host-only para apresentação e agente de defesa na Vítima. |
| 0:45–1:25 | Mostrar ping respondendo, envenenamento sem encaminhamento, detecção e defesa. Exibir ARP estático e deltas de descarte — não só recuperação do ping. |
| 1:25–2:05 | Explicar fuzzy manual como baseline; AG/NSGA-II ajustam quatro parâmetros em 600 cenários sintéticos. Depois da ADR 0013 o manual subiu de F1 0,4950 para 0,6389; AG (0,6490) e NSGA-II (0,6400) ficam só 0,010 e 0,001 acima, trocando mais recall por mais falsos positivos e menor precisão. Mostrar Pareto e média/DP de 20 sementes sem afirmar superioridade. |
| 2:05–2:30 | Mostrar PR revisado, CI/CD e URL HTTPS com dados sintéticos. Distinguir cloud da rede isolada real. |
| 2:30–2:50 | Concluir com o que foi comprovado, limitações do dataset e o papel de cada padrão arquitetural; apresentar equipe e repositório. |

Se o cenário real levar mais tempo, editar a gravação com indicação dos cortes
e tempos reais; não simular o ping nem sugerir latência que não foi medida.
Confirmar com o docente se o vídeo da disciplina pode ser o mesmo pitch do
integrador; o limite de 3 minutos do regulamento continua valendo para a ExpoTech.

## Perguntas de sabatina — todos devem responder

1. **Qual a diferença entre Ethernet source e MAC alegado no ARP?** Um é a
   origem observada no quadro; outro é uma alegação. Confundi-los falseia atribuição.
2. **Por que não usar encaminhamento no ataque?** Escolha deliberada para medir
   perda/recuperação de conectividade; MITM com forwarding pode manter o ping.
3. **Como o Sensor vê unicast?** Adaptador VirtualBox em Allow All e captura
   promíscua; a visibilidade precisa ser comprovada, não apenas configurada.
4. **Por que duas avaliações?** Reduz resposta a uma amostra isolada e ajuda a
   observar o efeito; não representa atraso fixo nem janelas independentes.
5. **Score >=65 basta para bloquear?** Não: exige alegação falsa de identidade
   confiável e MAC autorizado; outros MACs detectados geram threat_unmitigable.
6. **Por que ARP estático e firewall?** Um corrige o vínculo confiável; outro
   descarta quadros do MAC autorizado. Contadores verificam a segunda camada.
7. **Por que tcpdump ainda pode ver pacotes bloqueados?** O tap pode ocorrer
   antes do filtro; evidência usa deltas antes/depois do ponto de filtragem.
8. **Como funciona Mamdani?** Pertinências, cinco regras, min/max, agregação e
   centroide; ausência gera pertinência zero, não baixo risco inventado. Em R4/R5,
   desvio e razão ausentes são neutros (ADR 0013): conhecido calado é confiável,
   mas conflito e frequência continuam obrigatórios.
9. **NEW ou UNKNOWN?** MAC ausente após consulta válida é NEW; UNKNOWN indica
   falta real de informação/falha. Promoção a KNOWN é confirmação explícita.
10. **Qual a unidade do baseline?** Bytes por segundo; mediana de cinco janelas
    completas elegíveis, dividindo bytes pela duração antes de obter a mediana.
11. **Quais são os quatro genes?** Saturação de conflito [0,1;1], frequência
    [1;20]/s, desvio [0,25;4] e limiar superior [50;85]. Limiar inferior 35 e rampa ratio 0,5–1
    permanecem fixos, conforme optimization/experiment.py e classifier.py.
12. **Por que baseline e otimização são comparáveis?** Mesmas regras/features,
    splits e métricas; baseline manual intacto. Teste não escolhe parâmetros.
13. **AG e NSGA-II fazem o quê?** AG maximiza F1; NSGA-II busca recall alto e FPR
    baixo com soluções não dominadas. Uma solução é escolhida na validação.
14. **Por que 20 sementes e desvio-padrão?** Medem variabilidade da busca;
    não transformam corpus sintético em evidência de generalização real.
15. **O que havia de errado com ratio=1 constante?** Saturava a anomalia,
    mascarava genes e fechava regras. O corpus vigente contém requests/replies.
    Com o modelo da ADR 0013 o manual chegou a F1 0,6389 e os otimizadores ficam
    marginalmente acima (GA +0,010, NSGA-II +0,001), com FPR maior: não afirmar
    que otimizar vence o manual.
16. **O otimizado substitui o manual no dashboard?** Não. Compartilha Strategy,
    mas a comparação é offline e o pipeline operacional mantém o manual.
17. **Onde estão Observer/Strategy/Repository?** EventBus/Socket.IO; contratos de
    análise/mitigação; persistência SQL e providers de reputação/baseline.
18. **Por que CSRF antes do login?** Login também é POST; frontend busca token,
    envia header, e sessão/token são renovados após autenticação.
19. **O que a nuvem comprova?** Deploy/container/CI/CD e aplicação com dados
    sintéticos; não comprova nftables ou ataque real. Não existe túnel para o lab.
20. **Por que um worker/instância?** Fonte e barramento são locais ao processo;
    várias réplicas duplicariam produção e exigiriam coordenação adicional.
21. **Por que o gateway não fica vermelho durante o ataque?** Ele alega o mesmo IP
    que o Atacante, mas é reconhecido (KNOWN) e o Atacante não: pela ADR 0013 o
    conflito daquele IP pesa só no não reconhecido. Sem sinal ruim, o gateway fica
    confiável. Limite: se o atacante também fosse KNOWN, o conflito valeria para
    os dois.

## Rodada de estudo

Cada integrante desenha o pipeline sem consultar documentos, responde perguntas
fora do próprio módulo e reproduz uma verificação. Outro integrante faz revisão.
Repetir até que todos expliquem hipóteses, resultados, limites e evidências sem
usar apenas nomes de tecnologias. Confirmar presença de todos na avaliação.

Não decorar superioridade incondicional: o resultado atual é um trade-off.
Não apresentar tabelas de historical-invalid/ como comparação vigente.
