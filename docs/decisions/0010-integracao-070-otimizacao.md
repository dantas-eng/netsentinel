# ADR 0010 — Integração local da base 0.7.0 e extensão de otimização

> **Retificação — ADR 0011:** a comparação com ratio constante foi invalidada.
> O empate é artefato de medição. O texto abaixo registra a integração histórica;
> para corpus, decisão sobre genes e comparação vigentes, consultar a ADR 0011.

## Status e origens

Aceita para integração local autorizada pelo grupo. Não há repositório Git,
branches remotos, tag ou publicação comprovada. O ZIP final é preparado para o
primeiro commit a ser realizado pelo grupo; nenhuma publicação foi executada.

As duas linhas partiram da base comum 0.6.0 informada pelo grupo:

1. `netsentinel-main.zip`: versão operacional 0.7.0, com detecção ampla/mitigação
   restrita, SecurityIdentity/trusted_bindings(), ratio ARP, corpus Python/JS,
   CSP, poda de eventos e telemetria.
2. Extensão derivada da 0.6.0: `optimization/`, dataset sintético, AG/NSGA-II,
   relatório e fronteira empírica. Origem entregue em `NetSentinel_Optimization.zip`.

Essa proveniência descreve linhagens de arquivos, não histórico de commits.

## Compatibilidade verificada

Não há colisão de caminhos em `src/netsentinel/optimization`, `research/` e
`requirements-optimization.txt`. Entretanto, ausência de conflito textual não
significa compatibilidade semântica: a extensão importa FeatureExtractor,
RiskInputs e evaluate da aplicação. Na 0.7.0, RiskInputs inclui arp_reply_ratio,
o extrator calcula replies/(requests+replies), e evaluate exige memberships['ratio'].
R2/R3 incluem ratio alto no OR; R4/R5 incluem ratio baixo no AND. Copiar o módulo
antigo sem adaptação causaria KeyError e comparações inconsistentes.

## Decisão sobre genes e baseline

Manter os quatro genes aprovados, respectivas faixas, seleção e operadores.
A nova feature é uma quinta entrada, mas não exige um quinto gene. Sua pertinência
reutiliza diretamente ramp_from e RATIO_HIGH_FLOOR da base 0.7.0:

- alto = clip((ratio − 0,5)/(1 − 0,5), 0, 1);
- baixo = 1 − alto para input presente;
- input ausente: ambos zero.

Piso 0,5 e teto 1 são fixos, não otimizados. Isso evita introduzir uma dimensão
experimental não aprovada e garante que os parâmetros manuais reproduzam o novo
baseline. O mutador continua com probabilidade por gene 1/4. As cinco regras são
importadas, não copiadas ou reescritas no módulo de otimização.

O baseline da comparação atual é FuzzyRiskStrategy da 0.7.0, preservado sem edição.
O baseline 0.6.0 e suas métricas não podem ser tratados como resultados da 0.7.0.
A estratégia parametrizada permanece exclusivamente offline; nenhuma alteração
é feita em SecurityIdentity, trusted_bindings(), mitigação, backend ou dashboard.

## Dataset e resultados

O corpus original e resultados 0.6.0 são conservados em `research/historical-v060/`.
A geração atual mantém semente, cenários, rótulos, split e PCAPs, mas extrai também
ratio pela captura atual. Não preencher ratio ausente em manifesto antigo com
zero ou valor inventado: regenerar as features via PCAP.

Limitação relevante: o gerador original só emite replies ARP. Assim ratio=1 nos
600 cenários, inclusive benignos; a nova regra pode aumentar falsos positivos e
reduzir a utilidade dos genes existentes. Isso é documentado, não corrigido
alterando silenciosamente o corpus ou os resultados. Diversificar requests/replies
é trabalho experimental posterior, com novo dataset e nova comparação.

A comparação é reexecutada com 20 sementes por algoritmo, população 40, 40 gerações,
e mesmos operadores. Os resultados atuais ficam separados em `research/results/`.
Não é experimento de generalização em rede real; a repetição não valida as VMs.

## Documentação e conflitos

Preservar ADR 0008 da base 0.7.0 (detecção ampla/mitigação restrita).
Renumerar a antiga ADR 0008 do ramo de otimização como ADR 0009, com nota de origem.
Esta ADR 0010 registra a integração. Corrigir compliance, README e roteiro de
apresentação para retirar alegações de repositório, tags, PR, proteção de branch e
CI remota inexistentes. Workflow escrito é preparação, não execução comprovada.

## Validação e limites

Executar integralmente os testes Python da base, testes JS, testes de otimização,
Ruff e build do frontend; registrar números medidos em `research/VALIDATION.md`.
Os testes de paridade devem incluir ratio ausente, zero, piso, teto e valores
intermediários. Verificar hashes dos PCAPs entre origens para separar mudança de
regra de mudança de dataset. Resultados históricos permanecem intactos.

Docker/Postgres real, VMs, proteção de branch, execução remota de CI e deploy
cloud continuam pendentes. A integração não autoriza mitigação fora do laboratório.
