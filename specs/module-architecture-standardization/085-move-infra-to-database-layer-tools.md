# 085 — move-infra-to-database-layer-tools

## Tipo

refactor

## Objetivo

Mover persistência de `tools` de `infra/models.py`, `repositories.py` e `mappers.py` para `infra/database`.

## Contexto

O módulo `tools` será padronizado sem perder ownership de domínio. Estado conhecido: Tool, Secret; tabelas tools.tools, tools.secrets; cross-FKs: tools.tools.project_id -> core.projects.id; tools.tools.agent_id -> ai.agents.id (legada); tools.secrets.project_id -> core.projects.id.

## Pré-condições

- 084 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
find src/modules/tools -maxdepth 5 -type f | sort
rg "modules\.tools|from modules\.|ForeignKey\(|event_type|UnitOfWork" src/modules/tools tests -g "*.py"
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- src/modules/tools/**
- tests/modules/tools/**
- tests/architecture/**
- migrations/versions/* apenas quando explicitamente necessário
- execution/runtime.md

## Alterações proibidas

- não fundir bounded contexts apenas para igualar diretórios
- não criar base repository/UoW genérico com semântica de domínio
- não executar rename destrutivo de tabela ou coluna sem expand-migrate-contract
- não modificar tabelas de outro módulo
- não usar o agent como repository/service remoto
- não alterar regra de negócio de outro módulo
- não importar internals de outro módulo
- não mover domínio para shared
- não colocar worker concreto em src/workers ou shared/workers
- não alterar contrato público sem shim/deprecation e teste de compatibilidade
- não criar comunicação síncrona direta entre módulos para mudança de estado
- não criar Foreign Key física para tabela pertencente a outro módulo

## Plano de implementação

1. Copiar/mover models mantendo metadata/table/schema.
2. Mover repositories concretos.
3. Mover mappers.
4. Atualizar migrations/env.py somente por import.
5. Criar shims temporários nos paths antigos.
6. Não renomear tabela nesta spec.

## Contratos esperados

- Bounded context `tools` continua independente.
- Entidades conhecidas: Tool, Secret.
- Tabelas conhecidas: tools.tools, tools.secrets.
- Referências cross-module a tratar: tools.tools.project_id -> core.projects.id; tools.tools.agent_id -> ai.agents.id (legada); tools.secrets.project_id -> core.projects.id.
- Rotas a preservar: rotas de tools e secrets, conforme inventário.
- UoW concreto coordena somente repositories, Inbox e Outbox do módulo.
- __tablename__ e schema permanecem iguais.
- Repositories implementam ports do domain.
- Mappers não contêm regra de negócio.

## Testes obrigatórios

- tests/modules/tools/integration/database/test_repositories.py
- tests/architecture/test_tools_database_location.py

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
pytest tests/modules/tools -q
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- SQLAlchemy metadata contém mesmas tabelas
- Alembic não gera drop/create espúrio
- nenhum repository concreto fora de infra/database

## Rollback

1. Restaurar paths antigos a partir do commit anterior.
2. Reativar shim/route anterior.
3. Executar downgrade apenas para migration criada nesta spec e validada como reversível.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `085`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `086`.
