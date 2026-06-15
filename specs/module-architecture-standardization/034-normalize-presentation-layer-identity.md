# 034 — normalize-presentation-layer-identity

## Tipo

refactor

## Objetivo

Normalizar presentation de `identity` em routes, controllers, schemas e mappers.

## Contexto

O módulo `identity` será padronizado sem perder ownership de domínio. Estado conhecido: User, Organization, OrganizationMember, OrganizationInvite, UserSession; tabelas identity.users, identity.organizations, identity.organization_members, identity.organization_invites, identity.user_sessions; cross-FKs: nenhuma FK cross-module conhecida no model inspecionado; confirmar inventário.

## Pré-condições

- 033 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
find src/modules/identity -maxdepth 5 -type f | sort
rg "modules\.identity|from modules\.|ForeignKey\(|event_type|UnitOfWork" src/modules/identity tests -g "*.py"
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- src/modules/identity/**
- tests/modules/identity/**
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

1. Congelar OpenAPI/contratos atuais.
2. Atualizar controllers para application DTOs/use cases.
3. Manter routes finas.
4. Mover schemas/mappers para paths canônicos.
5. Adicionar testes HTTP de compatibilidade.

## Contratos esperados

- Bounded context `identity` continua independente.
- Entidades conhecidas: User, Organization, OrganizationMember, OrganizationInvite, UserSession.
- Tabelas conhecidas: identity.users, identity.organizations, identity.organization_members, identity.organization_invites, identity.user_sessions.
- Referências cross-module a tratar: nenhuma FK cross-module conhecida no model inspecionado; confirmar inventário.
- Rotas a preservar: rotas de autenticação, usuários, organizações, membros e convites, conforme inventário.
- UoW concreto coordena somente repositories, Inbox e Outbox do módulo.
- Controllers implementam Controller.handle(Request)->Response.
- Routes apenas chamam composer/adapters.
- Prefixos/status/body preservados.

## Testes obrigatórios

- tests/modules/identity/contract/test_routes.py
- tests/modules/identity/unit/presentation/test_controllers.py

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
pytest tests/modules/identity -q
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- OpenAPI não perde operações
- controller não importa repository/model
- rotas registradas uma vez

## Rollback

1. Restaurar paths antigos a partir do commit anterior.
2. Reativar shim/route anterior.
3. Executar downgrade apenas para migration criada nesta spec e validada como reversível.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `034`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `035`.
