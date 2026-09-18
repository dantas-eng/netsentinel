# ADR 0005 — Baseline persistido, unidades e migrações

Status: parâmetros aprovados pelo grupo e implementados na versão 0.4.0.

Calibração iniciada explicitamente pelo operador autenticado, somente para KNOWN.
Coletar cinco janelas completas de 8 s, íntegras, sem sobreposição e sem conflito
ARP observado na rede. Cada amostra é convertida por bytes_da_janela / 8 antes
de calcular a mediana. O contrato get_baseline_bps permanece em **bytes/s**.

Persistir amostras, execução de captura, intervalos monotônicos, data e auditoria.
Depois de pronta, a referência é congelada: tráfego subsequente não a atualiza.
Recalibração explícita mantém o valor anterior até reunir cinco novas amostras.
Mediana zero substitui o valor por indisponível (NULL); não inventar denominador.
Uma janela íntegra sem quadros de um MAC conhecido corresponde a zero bytes dessa
origem. Não confundir isso com janela incompleta, que é descartada.

A primeira janela aceita deve começar após o instante de solicitação; portanto a
coleta exige pelo menos 40 s de janelas, além da espera até a próxima amostra
publicada. Janelas inválidas aumentam o tempo necessário. A inferência da quinta
janela usa o baseline anterior; o novo valor passa a valer nos próximos snapshots.

Mudança da execução da captura interrompe a calibração. Reinício do serviço não
retoma uma coleta com outro relógio monotônico. Revogação de KNOWN cancela coleta
ativa e impede o provider de servir seu baseline enquanto o dispositivo for NEW;
as amostras históricas permanecem para auditoria.

Persistência: SQLAlchemy 2 com SQLite local e PostgreSQL/psycopg no cloud.
Alembic mantém o mesmo schema, com render_as_batch para futuras mudanças SQLite.
Migrações são explícitas; a factory da API não usa create_all. A revisão inicial
é fixa e não importa os modelos atuais para criar tabelas, evitando reescrever
implicitamente o histórico de schema.

Teste de unidade: [80,160,240,320,400] bytes -> [10,20,30,40,50] bytes/s -> mediana
30 bytes/s. Um teste integrado confirma que 480 bytes/8 s, comparados com baseline
30 bytes/s, produzem desvio relativo 1 no motor fuzzy.

Limite desta entrega: migração executada em SQLite e SQL PostgreSQL gerado offline.
Ainda é necessário aplicar e testar contra uma instância PostgreSQL real antes
do deploy cloud. O MVP usa um processo e uma fonte, sem coordenação distribuída.
