# 015 — execute-application-cutover-and-observability-window

## Tipo

deployment

## Objetivo

Fazer o cutover da aplicação para o schema agent e observar estabilidade antes da remoção do legado.

## Contexto

As views temporárias existem para desacoplar migration de deploy; removê-las imediatamente elimina o benefício do protocolo.

## Pré-condições

- 014 completed

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

1. Deployar código que referencia somente `agent` após migrations expand.
2. Executar smoke tests de rotas agent/knowledge/runtime preservadas no HTTP.
3. Monitorar erros SQL, locks, latência, filas, retries, duplicação de eventos e throughput.
4. Comparar métricas de leitura/escrita e contagens de eventos com baseline.
5. Definir janela mínima de observação e critérios objetivos de rollback.
6. Bloquear contract se qualquer acesso aos schemas legados for observado em logs/pg_stat_statements.

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

- Aplicação opera sem depender das views legadas.
- Nenhuma regressão funcional crítica.
- Critérios de contract migration formalmente aprovados.

## Rollback

1. Não executar contract/drop se a fase expand não estiver validada.
2. Antes da spec 016, preferir migration compensatória ou `SET SCHEMA` reverso conforme runbook.
3. Após a spec 016, rollback de dados depende de snapshot/restore ou migration compensatória explicitamente testada.
4. Registrar sempre o ponto de restauração e o SHA da aplicação compatível.

## Atualização obrigatória de runtime.md

Atualizar `/specs/agent-schema-consolidation/execution/runtime.md` com status da spec `015`, SHA, arquivos, migrations, consultas executadas, exit codes, critérios de aceite, riscos e próxima recomendada: `016`.
