# ADR 0004 — Promoção manual e persistida de reputação

Status: política definida nesta etapa, conforme solicitação do grupo para definir
a promoção NEW -> KNOWN. Repository e API implementados na versão 0.4.0; dashboard visual implementado na versão 0.5.0.

## Regra

MAC sem registro, após consulta bem-sucedida, retorna Reputation.NEW. Ao persistir
a primeira observação, o registro continua NEW. Nenhum número de observações,
classificações de baixo risco ou tempo de presença promove um dispositivo.

NEW -> KNOWN exige confirmação explícita de um operador autenticado no dashboard,
após reconhecer o dispositivo. Persistir MAC, instante UTC, identidade do operador
e motivo da confirmação. Permitir revogação manual de KNOWN -> NEW com o mesmo
registro de auditoria. Revogar não apaga histórico de eventos ou observações.

KNOWN significa dispositivo reconhecido, não isento de risco. Continuam aplicáveis
as regras fuzzy para frequência, conflito e desvio. UNKNOWN permanece reservado a
falha de consulta do provider; não gravar falha temporária como reputação persistente.

## Inventário inicial do laboratório

Permitir importação explícita dos três nós legítimos da configuração confiável
(Gateway, Vítima e Sensor) como KNOWN, registrada como bootstrap do operador.
Não executar promoção a cada inicialização: reimportações não devem sobrescrever
uma revogação manual. O Atacante não integra esse inventário reconhecido.

## Justificativa

Ausência de conflito por N janelas não comprova identidade ou autorização. A
promoção manual evita transformar presença na rede ou persistência no banco em
confiança automática. É uma regra simples e auditável para o MVP, consistente com
a ADR 0002 e com a distinção entre observação e julgamento.

## Critérios de aceitação para a implementação

- Consultar MAC ausente, persistir, reiniciar e consultar novamente: permanece NEW.
- Confirmar, reiniciar e consultar: KNOWN persistido.
- Revogar e reimportar inventário: permanece NEW até nova confirmação explícita.
- Banco indisponível: provider retorna UNKNOWN, sem inventar histórico.
- Toda confirmação/revogação gera auditoria; clientes sem autenticação não alteram reputação.

Não foi adotada nesta ADR uma fórmula de baseline de volume. A calibração e a
tecnologia de acesso SQLite/Postgres foram aprovadas posteriormente na ADR 0005.

## Implementação e exceção de sessão HTTP — versão 0.4.0

Repository e endpoints de confirmação/revogação implementados; a interface visual
foi adicionada na versão 0.5.0. A credencial única é configurada por OPERATOR_USERNAME
e OPERATOR_PASSWORD_HASH (Werkzeug), com SECRET_KEY externo ao código.

No modo **lab**, configurar explicitamente SESSION_COOKIE_SECURE=False porque o
acesso Host-only aprovado usa HTTP sem TLS. HttpOnly=True e SameSite=Lax continuam
ativos. Isso é uma exceção restrita ao laboratório, no mesmo contexto da ADR 0003,
não uma configuração recomendada para publicação. No modo **cloud**, Secure=True.

Login e alterações exigem CSRF; o token é renovado no login. A sessão dura uma hora.
Logout desconecta as conexões Socket.IO daquela sessão. WebSocket exige sessão e
CSRF na conexão e não oferece operações de alteração. Confirmação e calibração
ocorrem apenas pelas rotas HTTP autenticadas e protegidas.

O teste de integração verifica os atributos Set-Cookie em HTTP, a continuidade da
sessão entre requisições e a rejeição de alterações sem CSRF. Não foi realizado
ensaio com navegador nas VMs nesta entrega.
