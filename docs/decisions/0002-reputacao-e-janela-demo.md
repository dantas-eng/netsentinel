# ADR 0002 — Semântica de reputação e janela da demo

Status: aprovado pelo grupo em 09/09/2026.

## Contrato para o futuro Repository

Uma consulta bem-sucedida que não encontra histórico para um MAC deve retornar
Reputation.NEW. Ausência comum de histórico não é Reputation.UNKNOWN.
UNKNOWN fica reservado para indisponibilidade/falha real do provider, como banco
inacessível. Não converter falha de consulta em NEW nem ausência de registro em
UNKNOWN. O provider deve preservar a distinção entre esses casos.

As regras R2 e R4 exigem NEW. Retornar UNKNOWN para dispositivos nunca vistos
eliminaria sua ativação; em especial, impediria a cobertura de frequência anômala
sem conflito observado. R1 não exige reputação, mas a detecção de conflito na
janela depende de observar MACs distintos alegando o mesmo IP. Não presumir que
um envenenamento sempre produzirá essa evidência na captura do Sensor.

O motor fuzzy aprovado permanece inalterado. A semântica acima deve ser coberta
por testes do provider quando o módulo de repositório for implementado. A política
que promove NEW a KNOWN ainda deve ser definida nessa etapa; não confiar
implicitamente em um dispositivo somente por persistir sua primeira observação.

## Janela da demonstração

window_seconds = 8 segundos para a demo ao vivo. Configurar explicitamente
--window-seconds 8 na captura. Essa decisão não muda o padrão geral da CLI,
que continua exigindo o parâmetro, nem invalida as fixtures anteriores com 10 s.

A janela reduz o tempo de aquecimento inicial e oferece um intervalo para medir
frequência. Pode ser ajustada após validação nas VMs, registrando a alteração.
A classificação ocorre em snapshots de janela móvel; 8 segundos não representam
um temporizador obrigatório de espera após cada início de ataque.

## Pendências preservadas

Validar no VirtualBox a visibilidade unicast, a presença ou ausência de alegação
legítima do Gateway na janela e a frequência real dos anúncios do Atacante.
A ADR 0001 permanece vigente: ataque sem encaminhamento, defesa na Vítima e prova
separada de recuperação de ping, entrada ARP estática e descartes no firewall.
