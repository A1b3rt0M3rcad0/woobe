# 097 — standardize-bootstrap-dependency-injection-and-config

## Tipo

bootstrap

## Objetivo

Padronizar registro de rotas, UoW factories, registries e settings sem service locator cross-module.

## Contexto

Após padronização local, contratos transversais precisam convergir sem criar um framework genérico de domínio.

## Pré-condições

- 030-089 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
find src/modules/tools -maxdepth 5 -type f | sort
rg "modules\.tools|from modules\.|ForeignKey\(|event_type|UnitOfWork" src/modules/tools tests -g "*.py"
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- src/shared/**
- src/modules/*/infra/messaging/**
- src/modules/*/infra/workers/**
- src/modules/*/infra/database/**
- migrations/versions/**
- tests/**
- execution/runtime.md

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

1. Usar inventários 013-017 como fonte.
2. Definir contrato único sem semântica de domínio em shared.
3. Migrar um módulo por vez com compatibilidade.
4. Adicionar testes de falha, duplicidade e concorrência.
5. Eliminar configuração hard-coded global de módulos/eventos.
6. Atualizar documentação e runtime.

## Contratos esperados

- Exchange `domain.events` do tipo topic.
- Routing key `<producer>.<event>.v<version>`.
- Queue `<consumer>.<producer>-events` ou nome explicitamente inventariado.
- DLQ `<queue>.dlq`.
- Publisher confirms obrigatórios.
- FK cross-module proibida.

## Testes obrigatórios

- tests/integration/messaging/test_standardize_bootstrap_dependency_injection_and_config.py
- tests/architecture/test_cross_cutting_contracts.py

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
pytest tests/integration/messaging -q
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- Padronizar registro de rotas, UoW factories, registries e settings sem service locator cross-module.
- todos os módulos aderentes têm configuração explícita
- nenhuma regressão de mensagens pendentes
- testes de concorrência passam

## Rollback

1. Desabilitar contrato novo por configuração.
2. Restaurar registry/topologia anterior sem apagar queues.
3. Reaplicar constraint somente se não cruzar módulo; cross-FK não pode ser rollback arquitetural final.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `097`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `098`.
