# ADR 0007 — Duas avaliações consecutivas antes da mitigação

Status: aprovado pelo grupo; implementado na versão 0.6.0.

## Decisão

`SecurityDemo.consume()` exige duas avaliações consecutivas qualificando para o
mesmo MAC antes de chamar `mitigation.apply()`. Cada avaliação deve satisfazer:
MAC do Atacante configurado, alegação falsa do IP conhecido do Gateway originada
nesse MAC (`false_claim=true`) e score fuzzy não nulo >=65.

Uma avaliação que não qualifica zera a contagem. Ausência de resultado, score
nulo/abaixo de 65 e ausência da alegação falsa rompem a sequência. Mudança do MAC
reinicia a contagem em uma avaliação para o novo alvo. Estado fica em memória:
reiniciar o processo não preserva uma sequência parcial.

Após aplicação bem-sucedida, zerar a sequência e manter as consultas de status
já existentes, sem aplicar novamente enquanto a mitigação estiver confirmada.
Se a mitigação deixar de estar confirmada, são necessárias duas novas avaliações
qualificantes. Falha na chamada apply mantém a sequência qualificada para permitir
retentativa na próxima avaliação, como já previsto; uma avaliação não qualificante
intermediária também cancela essa sequência de retentativa.

## Justificativa

Dar suporte à prova visual de queda e recuperação do ping acordada desde a ADR
0001, com backend/dashboard já iniciados antes do ataque. Além disso, evitar
reação a uma avaliação ruidosa isolada, independentemente da apresentação.
A origem Ethernet, a alegação falsa e o limiar permanecem exigências conjuntas.

## Limite temporal

Duas avaliações não significam duas janelas completas sem sobreposição, nem um
atraso de 16 segundos. A janela continua sendo de 8 segundos; avaliações podem
compartilhar observações. Esta decisão acrescenta confirmação consecutiva, sem
introduzir timer, pausa manual ou garantia de independência estatística.
A duração real da perda de ping ainda precisa ser medida nas VMs; a mudança não
comprova, sozinha, interrupção perceptível durante a demo.

## Verificação

`tests/unit/test_security_consecutive.py` cobre duas qualificações, reset após
falha de qualificação, limiar, score nulo/ausente, MAC diferente, retentativa e
perda de mitigação. Integrações PCAP/Scapy → fuzzy → Strategy → agente e backend/
Socket.IO agora comprovam ausência de mitigação na primeira avaliação e aplicação
na segunda. Kernel e rede do agente continuam simulados nesses testes.
