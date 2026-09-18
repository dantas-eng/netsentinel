# ADR 0001 — ARP spoofing sem encaminhamento

Status: aprovado pelo grupo em 09/09/2026.

## Decisão

O cenário do MVP usa envenenamento do cache ARP da Vítima sem encaminhamento
ativo no Atacante. O Atacante não repassa o tráfego recebido. A implementação
posterior deve verificar essa condição antes do ensaio, incluindo ausência de
outro mecanismo de retransmissão que preserve a conectividade.

O laboratório permanece composto por quatro VMs Linux (Atacante, Vítima,
Gateway e Sensor) em uma Internal Network do VirtualBox, sem uplink de internet.
O Sensor usa Allow All e captura passiva. Nenhum cenário ofensivo sai dessa rede.

## Motivo e alternativa descartada

MITM com encaminhamento pode manter o ping funcionando e, portanto, não fornece
a interrupção visual aprovada. Essa alternativa fica fora do MVP por aumentar
as condições necessárias à demonstração. A escolha prioriza confiabilidade da
demo e o prazo do semestre; não decorre de desconhecimento da interceptação.
O efeito demonstrado é negação de conectividade por envenenamento ARP, não
interceptação transparente ou leitura de conteúdo.

## Validação prevista

Manter ping contínuo da Vítima para o Gateway: funcionar antes, falhar durante o
envenenamento e recuperar após a mitigação. Confirmar também a associação ARP
estática legítima, os contadores de descarte e a ausência de entrega do tráfego
bloqueado após o firewall da Vítima. O Sensor pode continuar vendo tentativas.
A recuperação do ping não prova, isoladamente, a eficácia da camada de firewall.

A defesa será uma implementação concreta de MitigationStrategy: o backend chama
a API HTTP do agente local da Vítima, que aplica ARP estático e bloqueio de MAC e
devolve contadores. A implementação e a prova ao vivo ainda estão pendentes.

## Consequências

Esta decisão não altera o módulo de captura aprovado. A validação VirtualBox
pode ser executada pela frente de segurança enquanto o motor fuzzy é desenvolvido.
O motor receberá reputação e baseline por providers injetados; não dependerá da
implementação antecipada de Repository. Permanecem fora do escopo desta decisão
os parâmetros fuzzy, a tecnologia de firewall e os controles de acesso da API.
