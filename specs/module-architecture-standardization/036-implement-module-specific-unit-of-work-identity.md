# 036 — implement-module-specific-unit-of-work-identity

## Tipo

refactor

## Objetivo

Implementar `IdentityUnitOfWork` e torná-lo boundary transacional efetivo.

## Contexto

O módulo `identity` será padronizado sem perder ownership de domínio. Estado conhecido: User, Organization, OrganizationMember, OrganizationInvite, UserSession; tabelas identity.users, identity.organizations, identity.organization_members, identity.organization_invites, identity.user_sessions; cross-FKs: nenhuma FK cross-module conhecida no model inspecionado; confirmar inventário.

## Pré-condições

- 035 completed

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

1. Criar unit_of_work.py com session factory.
2. Expor repositories próprios lazy.
3. Expor Inbox/Outbox próprias.
4. Atualizar composers para UoW específico.
5. Garantir rollback automático.
6. Remover commit manual duplicado.

## Contratos esperados

- Bounded context `identity` continua independente.
- Entidades conhecidas: User, Organization, OrganizationMember, OrganizationInvite, UserSession.
- Tabelas conhecidas: identity.users, identity.organizations, identity.organization_members, identity.organization_invites, identity.user_sessions.
- Referências cross-module a tratar: nenhuma FK cross-module conhecida no model inspecionado; confirmar inventário.
- Rotas a preservar: rotas de autenticação, usuários, organizações, membros e convites, conforme inventário.
- UoW concreto coordena somente repositories, Inbox e Outbox do módulo.
- Classe `IdentityUnitOfWork`.
- Nenhum repository de outro módulo é exposto.
- State + Outbox ou Inbox + state + Outbox usam uma transação.

## Testes obrigatórios

- tests/modules/identity/integration/database/test_unit_of_work.py
- tests/modules/identity/integration/test_outbox_atomicity.py

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

- composers não usam PostgresUnitOfWork genérico
- rollback remove estado e Outbox
- commit único por handler

## Rollback

1. Restaurar paths antigos a partir do commit anterior.
2. Reativar shim/route anterior.
3. Executar downgrade apenas para migration criada nesta spec e validada como reversível.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `036`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `037`.
