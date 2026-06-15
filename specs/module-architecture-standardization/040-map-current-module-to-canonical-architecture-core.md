# 040 — map-current-module-to-canonical-architecture-core

## Tipo

discovery

## Objetivo

Mapear o módulo `core` para a arquitetura canônica sem alterar código.

## Contexto

O módulo `core` será padronizado sem perder ownership de domínio. Estado conhecido: Project, ApiKey; tabelas core.projects, core.api_keys; cross-FKs: core.projects.organization_id -> identity.organizations.id; core.api_keys.created_by_user_id -> identity.users.id.

## Pré-condições

- 020-029 completed
- 010-019 inventories current

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

1. Criar current-to-target map por arquivo.
2. Classificar cada classe/função por camada real.
3. Listar imports, rotas, tabelas, eventos, workers e testes.
4. Classificar movimentos como move, split, keep, shim ou delete.
5. Registrar riscos e ordem interna.

## Contratos esperados

- Bounded context `core` continua independente.
- Entidades conhecidas: Project, ApiKey.
- Tabelas conhecidas: core.projects, core.api_keys.
- Referências cross-module a tratar: core.projects.organization_id -> identity.organizations.id; core.api_keys.created_by_user_id -> identity.users.id.
- Rotas a preservar: rotas de projetos e API keys, conforme inventário.
- UoW concreto coordena somente repositories, Inbox e Outbox do módulo.
- Saída: execution/inventory/core-migration-map.md.

## Testes obrigatórios

- tests/architecture/test_inventory_artifacts.py::test_core_migration_map_exists

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

- core-migration-map.md existe
- cada arquivo atual tem destino/ação
- nenhum código de produção alterado

## Rollback

1. Restaurar paths antigos a partir do commit anterior.
2. Reativar shim/route anterior.
3. Executar downgrade apenas para migration criada nesta spec e validada como reversível.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `040`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `041`.
