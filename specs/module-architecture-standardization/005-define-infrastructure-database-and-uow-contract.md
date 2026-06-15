# 005 — define-infrastructure-database-and-uow-contract

## Tipo

architecture

## Objetivo

Definir contrato único para models, mappers, repositories e Unit of Work por módulo.

## Contexto

O agent possui `AgentUnitOfWork`, mas alguns composers ainda usam UoW genérico. Os demais módulos expõem models/repositories planos.

## Pré-condições

- 004 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
rg "PostgresUnitOfWork|UnitOfWork" src/modules -g "*.py"
find src/modules -path "*/infra*" -type f | sort
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- infra/database/*
- shared contracts técnicos mínimos

## Alterações proibidas

- não fundir bounded contexts apenas para igualar diretórios
- não criar base repository/UoW genérico com semântica de domínio
- não executar rename destrutivo de tabela ou coluna sem expand-migrate-contract
- não alterar regra de negócio de outro módulo
- não importar internals de outro módulo
- não mover domínio para shared
- não colocar worker concreto em src/workers ou shared/workers
- não alterar contrato público sem shim/deprecation e teste de compatibilidade
- não criar comunicação síncrona direta entre módulos para mudança de estado
- não criar Foreign Key física para tabela pertencente a outro módulo

## Plano de implementação

1. Definir repository interfaces no domínio.
2. Definir implementações SQLAlchemy em infra/database.
3. Definir UoW concreto por módulo.
4. Definir commit/rollback e repositories lazy.
5. Definir Outbox/Inbox na mesma transação.

## Contratos esperados

- <Module>UnitOfWork coordena somente tabelas do módulo.
- Composers usam o UoW concreto do módulo.
- Shared pode fornecer base técnica sem repositories de domínio.

## Testes obrigatórios

- tests/architecture/test_uow_ownership.py
- tests/integration/test_module_uow_transactions.py

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- nenhum UoW concreto atravessa módulos
- composers migrados não instanciam PostgresUnitOfWork genérico
- rollback desfaz estado e Outbox

## Rollback

1. Restaurar composers ao UoW anterior e manter facade compatível.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `005`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `006`.
