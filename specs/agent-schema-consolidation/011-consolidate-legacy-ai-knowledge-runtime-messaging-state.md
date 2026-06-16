# 011 — consolidate-legacy-ai-knowledge-runtime-messaging-state

## Tipo

messaging-migration

## Objetivo

Resolver e eliminar as tabelas Inbox/Outbox legadas de ai, knowledge e runtime sem perder eventos operacionais.

## Contexto

Há até seis tabelas legadas com nomes colidentes e contrato diferente das tabelas canônicas `agent.agent_outbox_events` e `agent.agent_inbox_events`; movê-las diretamente não é possível nem correto.

## Pré-condições

- 010 completed

## Branch e baseline obrigatórias

- branch de execução: `development_agent-schema-consolidation`
- baseline de origem: `development`
- SHA observado durante a criação do plano: `537e401356f956e928d1a7d025a3d9ccff2222aa`

Antes de alterar qualquer arquivo:

```bash
test "$(git branch --show-current)" = "development_agent-schema-consolidation"
git merge-base --is-ancestor 537e401356f956e928d1a7d025a3d9ccff2222aa HEAD
git status --short
git rev-parse HEAD
```

Se o guard falhar, marcar a spec como `blocked`.

## Estado atual a detectar

```bash
rg -n 'schema=["'](ai|knowledge|runtime)["']|(ai|knowledge|runtime)\.' src migrations tests -g '*.py'
rg -n 'ForeignKey\(|create_foreign_key|ForeignKeyConstraint' src migrations -g '*.py'
alembic current
alembic heads
```

Além desses comandos, executar os checks específicos descritos no plano. Persistir resultados nos arquivos de inventário da suite.

## Alterações permitidas

- migrations/versions/*agent_schema*
- src/modules/agent/infra/database/**
- src/modules/{tools,metering,observability}/infra/database/** quando exigido
- tests/architecture/**
- tests/integration/**
- scripts de migration/validação explicitamente inventariados
- specs/agent-schema-consolidation/execution/**

## Alterações proibidas

- não usar `DROP ... CASCADE` para ocultar dependências inesperadas
- não recriar tabelas com novos UUIDs quando `SET SCHEMA` é aplicável
- não criar dual write permanente
- não manter schema legado como solução final
- não criar FK física cross-module
- não alterar contratos HTTP sem requisito explícito
- não marcar conclusão sem validação de banco real ou fixture equivalente

## Plano de implementação

1. Congelar publishers/consumers legados e medir estados por status.
2. Para eventos pending/retryable, definir mapper explícito para envelope canônico, preservando event identity, idempotency, correlation, causation, payload e versão.
3. Bloquear a spec se um evento não puder ser mapeado sem perda semântica.
4. Não reenfileirar eventos completed/processed.
5. Exportar histórico necessário para retenção/auditoria antes de drop, com checksum e localização registrados.
6. Atualizar writers/workers para usar somente as tabelas canônicas do schema agent.
7. Validar deduplicação e ausência de publicação dupla durante o cutover.

## Contratos esperados

- `agent` é o único owner físico das tabelas do bounded context agent.
- FKs internas `agent -> agent` são permitidas e testadas.
- FKs entre módulos são proibidas; IDs externos são opacos.
- A cadeia Alembic é append-only salvo decisão formal de rebaseline.
- Cada mudança destrutiva depende de evidência da fase expand e de paridade de dados.

## Testes obrigatórios

- teste específico da spec;
- regressão de `tests/architecture`;
- regressão dos repositories/fluxos afetados;
- migration test quando houver alteração de catálogo.

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
alembic upgrade head
alembic current
```

Quando a spec exigir PostgreSQL real, executar também as consultas catalogadas no arquivo e registrar exit code/resultado. Comando indisponível deve virar pendência objetiva; não pode ser reportado como sucesso.

## Critérios de aceite objetivos

- Nenhum evento operacional fica preso em schema legado.
- Workers usam exclusivamente agent.agent_outbox_events/agent.agent_inbox_events.
- Histórico descartado possui política e evidência de retenção.

## Rollback

1. Não executar contract/drop se a fase expand não estiver validada.
2. Antes da spec 016, preferir migration compensatória ou `SET SCHEMA` reverso conforme runbook.
3. Após a spec 016, rollback de dados depende de snapshot/restore ou migration compensatória explicitamente testada.
4. Registrar sempre o ponto de restauração e o SHA da aplicação compatível.

## Atualização obrigatória de runtime.md

Atualizar `/specs/agent-schema-consolidation/execution/runtime.md` com status da spec `011`, SHA, arquivos, migrations, consultas executadas, exit codes, critérios de aceite, riscos e próxima recomendada: `012`.
