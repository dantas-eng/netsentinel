# ADR 0012 — Deploy acadêmico em Render Free e Supabase Free

- Data: 28/09/2026.
- Status: escolha aprovada pelo grupo nesta sessão; configuração preparada,
  publicação/validação real pendentes.
- Substitui a previsão de Cloud Run como provedor da entrega acadêmica.

## Contexto

O NEXUS exige nuvem e CI/CD, mas não impõe um provedor. O grupo prioriza evitar
gastos. Cloud Run oferece franquia gratuita, mas excedentes podem ser cobrados,
e uma fonte em segundo plano exige cuidado com o regime de CPU/faturamento.
A mudança é de hospedagem; Flask, Socket.IO, Docker, SQLAlchemy/Alembic e Postgres
permanecem. Não se conecta a aplicação cloud à rede isolada de ataque.

## Decisão

Usar um Web Service Render Free com o Dockerfile existente e Supabase Free para
Postgres, via Session pooler. APP_MODE=cloud, HTTPS e cookie Secure=True;
um worker/uma instância. Não criar banco Render Free: sua expiração de 30 dias
é inadequada ao calendário até novembro. Não contratar disco, domínio ou upgrade.

Desativar a Data API no projeto Supabase dedicado: os dados são acessados via
SQLAlchemy e pela API Flask autenticada. Usar conexão TLS; sem credenciais no Git.

O job de CD depende dos três checks existentes, só executa na main e exige
RENDER_DEPLOY_ENABLED=true. Render Auto-Deploy fica Off; o workflow envia o SHA
testado, aguarda live e confere o commit antes do smoke HTTPS. O primeiro deploy
de criação do serviço é bootstrap, não evidência de CD concluído. Ativar a variável
somente depois de configurar contas e secrets. Congelamento final desativa o CD.

## Consequências e limites

- Render Free pode dormir após 15 minutos sem tráfego e tem quotas compartilhadas.
  Supabase Free tem 500 MB e pode pausar após uma semana inativo. Não há promessa
  de serviço permanente ou custo zero fora das condições Free do provedor.
- Preferir contas sem forma de pagamento. Se cadastro exigir cartão/plano pago,
  interromper e reavaliar com o grupo. Sem keep-alive artificial ou upgrade automático.
- A fonte sintética produz eventos continuamente enquanto o processo está ativo.
  Acompanhar armazenamento e usar a poda manual já existente, preservando evidências.
- Reinícios/redeploys reiniciam a fonte, não o histórico. Durante troca de revisão
  o provedor pode manter instâncias antiga/nova transitoriamente: não colher
  evidência nem calibrar baseline nesse intervalo. Não escalar horizontalmente.
- A disponibilidade e os limites precisam ser conferidos antes da apresentação.
  O laboratório local continua sendo a demonstração da vulnerabilidade real.
- Testes offline do cliente de CD não comprovam API Render, banco Supabase,
  memória disponível no plano Free ou funcionamento de WebSocket no navegador.

## Referências oficiais consultadas em 28/09/2026

- https://render.com/docs/free
- https://render.com/docs/blueprint-spec
- https://api-docs.render.com/reference/create-deploy
- https://api-docs.render.com/reference/retrieve-deploy
- https://supabase.com/pricing
- https://supabase.com/docs/guides/database/connecting-to-postgres
- https://supabase.com/docs/guides/api/securing-your-api
- https://cloud.google.com/run/pricing

Procedimento: [guia cloud](../closure/cloud.md).
