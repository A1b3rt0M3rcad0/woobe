# 041 — create-canonical-module-skeleton-core

## Tipo

refactor

## Objetivo

Criar skeleton canônico do módulo `core` sem mover regra de negócio prematuramente.

## Contexto

O módulo `core` será padronizado sem perder ownership de domínio. Estado conhecido: Project, ApiKey; tabelas core.projects, core.api_keys; cross-FKs: core.projects.organization_id -> identity.organizations.id; core.api_keys.created_by_user_id -> identity.users.id.

## Pré-condições

- 040 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
find src/modules/core -maxdepth 5 -type f | sort
rg "modules\.core|from modules\.|ForeignKey\(|event_type|UnitOfWork" src/modules/core tests -g "*.py"
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- src/modules/core/**
- tests/modules/core/**
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

1. Criar packages application/domain/infra/database/infra/messaging/infra/workers/presentation.
2. Criar __init__.py mínimos.
3. Não criar classes abstratas vazias.
4. Adicionar teste de estrutura.
5. Manter paths legados ativos.

## Contratos esperados

- Bounded context `core` continua independente.
- Entidades conhecidas: Project, ApiKey.
- Tabelas conhecidas: core.projects, core.api_keys.
- Referências cross-module a tratar: core.projects.organization_id -> identity.organizations.id; core.api_keys.created_by_user_id -> identity.users.id.
- Rotas a preservar: rotas de projetos e API keys, conforme inventário.
- UoW concreto coordena somente repositories, Inbox e Outbox do módulo.
- src/modules/core/ | ├── application | │   ├── composers | │   ├── dtos | │   ├── handlers | │   └── use_cases | ├── domain | │   ├── entities.py | │   ├── enums.py | │   ├── errors.py | │   ├── events.py | │   ├── repositories.py | │   ├── services.py | │   └── value_objects.py | ├── infra | │   ├── database | │   │   ├── mappers.py | │   │   ├── models.py | │   │   ├── repositories.py | │   │   └── unit_of_work.py | │   ├── messaging | │   │   ├── consumers.py | │   │   ├── event_mappers.py | │   │   └── publishers.py | │   └── workers | │       ├── inbox_consumer.py | │       ├── inbox_processor.py | │       ├── outbox_dispatcher.py | │       └── registry.py | └── presentation |     ├── controllers |     ├── mappers.py |     ├── routes.py |     └── schemas.py

## Testes obrigatórios

- tests/architecture/test_module_structure.py::test_core_structure

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
pytest tests/modules/core -q
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- diretórios canônicos existem
- nenhum comportamento alterado
- testes atuais continuam passando

## Rollback

1. Restaurar paths antigos a partir do commit anterior.
2. Reativar shim/route anterior.
3. Executar downgrade apenas para migration criada nesta spec e validada como reversível.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `041`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `042`.
