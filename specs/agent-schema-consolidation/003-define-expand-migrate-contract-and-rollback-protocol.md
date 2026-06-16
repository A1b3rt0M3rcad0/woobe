# 003 — define-expand-migrate-contract-and-rollback-protocol

## Tipo

migration-design

## Objetivo

Definir a sequência segura de migration, compatibilidade, deploy e rollback.

## Contexto

`ALTER TABLE ... SET SCHEMA` preserva dados e identidade física, mas adquire locks e muda nomes qualificados. A aplicação precisa sobreviver durante a transição.

## Pré-condições

- 002 completed

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

1. Usar migrations append-only por padrão; não editar migrations já aplicadas sem evidência formal de que nenhum ambiente persistente depende delas.
2. Mover tabelas com `ALTER TABLE <legacy>.<table> SET SCHEMA agent` em transações controladas.
3. Após cada move, criar view simples e temporária no schema antigo (`CREATE VIEW ai.agents AS SELECT * FROM agent.agents`) somente quando necessária para compatibilidade de uma release.
4. Validar explicitamente que INSERT/UPDATE/DELETE/RETURNING usados pelo SQLAlchemy funcionam pelas views antes de depender delas.
5. Definir lock_timeout, statement_timeout, janela de manutenção, backup/snapshot e critério de abort.
6. Se uma tabela exceder o limite operacional definido no inventário, permitir estratégia copy/sync/cutover específica, documentada e testada.
7. Definir rollback por fase: antes do cutover de código, mover tabelas de volta; após contract/drop, rollback somente por restore ou migration compensatória.

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

- Runbook de deploy e rollback aprovado.
- Nenhuma etapa destrutiva ocorre antes de paridade e cutover.
- Compatibilidade temporária possui prazo de remoção.

## Rollback

1. Não executar contract/drop se a fase expand não estiver validada.
2. Antes da spec 016, preferir migration compensatória ou `SET SCHEMA` reverso conforme runbook.
3. Após a spec 016, rollback de dados depende de snapshot/restore ou migration compensatória explicitamente testada.
4. Registrar sempre o ponto de restauração e o SHA da aplicação compatível.

## Atualização obrigatória de runtime.md

Atualizar `/specs/agent-schema-consolidation/execution/runtime.md` com status da spec `003`, SHA, arquivos, migrations, consultas executadas, exit codes, critérios de aceite, riscos e próxima recomendada: `004`.
