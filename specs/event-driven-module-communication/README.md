# ProjectRAI — Event-Driven Module Communication

Pacote com **20 specs** para corrigir a comunicação entre módulos por Outbox, RabbitMQ e Inbox transacionais.

## Branch de execução

`development_event-driven-module-communication`

Criar a partir de `development` no SHA `cd8d5867967fea25ea170bd88ebc9a461ed16c09`:

```bash
git switch development
git pull --ff-only
test "$(git rev-parse HEAD)" = "cd8d5867967fea25ea170bd88ebc9a461ed16c09" || { echo "development avançou; revalidar inventário"; exit 1; }
git switch -c development_event-driven-module-communication
```

A branch dedicada não existia no remoto na geração do pacote.

## Fluxo obrigatório cross-module

```text
state + Outbox (mesma transação do producer)
→ dispatcher
→ RabbitMQ
→ consumer
→ Inbox commit
→ ACK
→ Inbox processor
→ use case consumidor + estado + optional Outbox + Inbox processed
  (mesma transação do consumer)
```

## Agent e Tool

Tool já pertence ao bounded context `agent`. O resultado da Tool é necessário de forma síncrona no loop do LLM. Portanto, a execução continua interna; apenas os fatos da execução destinados a `metering`, `observability` ou outros módulos saem por Outbox.

## Módulos afetados

- `agent`: producer principal; remover writes diretos, corrigir Outbox e transações de sync/stream/job.
- `metering`: consumer RabbitMQ, Inbox, handlers idempotentes e registry.
- `observability`: consumer RabbitMQ, Inbox e projeção idempotente de traces.
- `identity`, `core`, `billing`: remover self-subscriptions e handlers no-op; manter apenas integrações reais.
- `shared`/bootstrap: envelope, lifecycle de workers, topology e shutdown.
- banco: remover FKs cross-module.

Foram usadas exatamente 20 specs. A margem adicional de 15 não foi necessária.
