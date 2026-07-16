# MVP-00 — Evidências da baseline

Base SHA: `4076242edd156504a6eda353f7481cbd03784c1e`.

`development` e `development-mvp` estavam idênticas no início da etapa.

Verificações estáticas:

- frontend com login, registro, dashboard, agentes, playground, knowledge, tools, API keys, usage e traces;
- dashboard atual com dados estáticos, sem antecipar MVP-05/MVP-06;
- correção de idempotência presente em `event_mappers.py`;
- teste de regressão presente em `test_repeatable_mutation_idempotency.py`;
- backend com `/health` e routers dos módulos principais;
- Compose com API, workers, migration, PostgreSQL/pgvector, PgBouncer, RabbitMQ e web.

Riscos observados:

- `README.md` vazio;
- CI não comprovada;
- containers orientados a desenvolvimento;
- build, testes, migration e smoke ainda sem evidência executada.
