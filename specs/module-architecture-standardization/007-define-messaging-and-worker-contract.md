# 007 — define-messaging-and-worker-contract

## Tipo

architecture

## Objetivo

Padronizar Outbox dispatcher, RabbitMQ consumer, Inbox processor, handlers e registry por módulo.

## Contexto

Todos os módulos possuem Outbox/Inbox, mas workers e bindings não estão uniformes.

## Pré-condições

- 005 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
find src -path "*workers*" -type f | sort
rg "Outbox|Inbox|Consumer|Dispatcher|RabbitMQ|routing_key" src -g "*.py"
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- infra/messaging/*
- infra/workers/*
- shared/workers bases técnicas

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

1. Definir dispatcher/publisher/consumer/processor/handler/runner.
2. Definir ack somente após persistência da Inbox.
3. Definir publisher confirms.
4. Definir registry por módulo.
5. Definir runner central sem eventos específicos.

## Contratos esperados

- Workers concretos em modules/<module>/infra/workers.
- Bindings pertencem ao consumidor.
- Regra de negócio somente application/domain.

## Testes obrigatórios

- tests/architecture/test_worker_locations.py
- tests/integration/test_outbox_inbox_flow.py

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- nenhum worker concreto em shared/src/workers
- consumer salva Inbox antes de ack
- processor é idempotente

## Rollback

1. Desabilitar registry novo e reativar worker anterior sem remover dados pendentes.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `007`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `008`.
