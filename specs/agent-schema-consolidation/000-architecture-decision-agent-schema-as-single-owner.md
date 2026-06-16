# 000 — architecture-decision-agent-schema-as-single-owner

## Tipo

architecture

## Objetivo

Registrar a decisão mandatória de que todas as tabelas pertencentes ao bounded context `agent` ficam no schema PostgreSQL `agent`, eliminando os schemas operacionais legados `ai`, `knowledge` e `runtime`.

## Contexto

O código já está consolidado em `src/modules/agent`, porém `src/modules/agent/infra/database/models.py` ainda mapeia entidades para três schemas. O schema `agent` contém apenas Inbox/Outbox novas. A divisão física contradiz o ownership do módulo e mantém FKs artificiais entre partes do mesmo bounded context.

## Pré-condições

- nenhuma spec anterior

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

1. Definir `agent` como único schema operacional do bounded context.
2. Permitir FKs físicas somente entre tabelas que pertencem ao próprio schema/módulo `agent`.
3. Proibir FKs de `agent` para `core`, `identity` ou qualquer outro módulo; manter IDs externos como UUIDs opacos com índices locais.
4. Proibir FKs de outros módulos para tabelas `agent.*`.
5. Adotar expand-migrate-contract; nenhuma tabela com dados pode ser recriada por drop/create como primeira opção.
6. Congelar `ai`, `knowledge` e `runtime` como nomes legados sem novas tabelas, colunas, constraints ou código de runtime.

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

- ADR aceito e referenciado por todas as specs seguintes.
- Tabela final de ownership aprovada.
- Nenhuma ambiguidade entre FK intra-agent permitida e FK cross-module proibida.

## Rollback

1. Não executar contract/drop se a fase expand não estiver validada.
2. Antes da spec 016, preferir migration compensatória ou `SET SCHEMA` reverso conforme runbook.
3. Após a spec 016, rollback de dados depende de snapshot/restore ou migration compensatória explicitamente testada.
4. Registrar sempre o ponto de restauração e o SHA da aplicação compatível.

## Atualização obrigatória de runtime.md

Atualizar `/specs/agent-schema-consolidation/execution/runtime.md` com status da spec `000`, SHA, arquivos, migrations, consultas executadas, exit codes, critérios de aceite, riscos e próxima recomendada: `001`.
