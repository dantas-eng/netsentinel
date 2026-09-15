# ADR 0008 — Detecção ampla, mitigação restrita

Status: aprovado no design das melhorias 0.7.0.

## Contexto

Em `security/demo.py`, duas restrições estavam acopladas no mesmo bloco:
`results.get(self.config.attacker_mac)` descartava o score de qualquer outro
dispositivo, e `false_claim` só reconhecia falsificação do IP do Gateway
originada no MAC do Atacante configurado. Um atacante falsificando a Vítima, ou
um segundo dispositivo falsificando o Gateway, não era detectado.

## Decisão

Separar detectar de mitigar.

Detectar é amplo. `trusted_bindings()` expõe os quatro pares IP↔MAC já
validados. Qualquer alegação ARP cujo IP esteja nesse inventário e cujo
`claimed_mac` divirja do MAC confiável é falsificação; a origem (`source_mac`)
é registrada, mas não filtra a detecção. Todo `results` é avaliado. Ameaça
confirmada exige `score is not None and score >= 65` e falsificação atribuída
àquela origem.

Mitigar é estreito. Só o MAC autorizado por `LabConfig.require_attacker` /
`SecurityIdentity.attacker_mac` segue a sequência ADR 0007 e chama
`mitigation.apply()`. Qualquer outro MAC confirmado emite `threat_unmitigable`
com `reason='mac_not_pre_approved'`. A troca de MAC não some — a mitigação
ainda não resiste a ela — mas a detecção agora enxerga e declara a recusa.

A sequência ADR 0007 passa a ser `dict[str, int]` por MAC. Uma avaliação não
qualificatória zera só aquele MAC.

## Alternativa rejeitada

Generalizar a mitigação para qualquer MAC detectado. Isso viola a ADR 0003:
entregaria a escolha do alvo a um dado que o atacante controla.

## Verificação

`tests/unit/test_detection.py` cobre falsificação de cada papel, recusa de MAC
não pré-aprovado, duas ameaças simultâneas e sequência independente.
`tests/unit/test_security_consecutive.py` permanece inalterado.
