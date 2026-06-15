---
name: projectrai-outbox-inbox
description: Implement ProjectRAI Outbox/Inbox, RabbitMQ publishing, consumers, processors, worker registries, idempotency, retries, locking, and event envelopes.
license: MIT
compatibility: opencode
metadata:
  project: ProjectRAI
  phase: messaging-workers
  scope: outbox-inbox-rabbitmq
---

# ProjectRAI Outbox/Inbox and Workers

Use this skill for specs `050` through `063`, `072` through `073`, `080` through `085`, `090` through `109`, and tests around workers, messaging, idempotency, RabbitMQ topology, retries, and dead-letter handling.

The integration rule is strict: cross-module state changes happen through persisted Outbox events, RabbitMQ publication, persisted Inbox records, and module-owned processors. The producer does not know consumers. The consumer does not mutate producer tables.

## Required flow

1. A module changes only its own state.
2. In the same transaction, the module application layer persists an Outbox event through its own Unit of Work.
3. The module's outbox dispatcher claims pending/retryable events with locking.
4. The dispatcher publishes to RabbitMQ with publisher confirms.
5. The dispatcher marks an event as published only after broker confirmation.
6. A consuming module's inbox consumer receives the message, persists an Inbox record, and only then acknowledges the broker message.
7. The consuming module's inbox processor claims pending Inbox records, calls internal handlers/use cases, updates only its own state, and marks the Inbox status.

Never acknowledge a broker message before durable Inbox persistence. Never mark Outbox published before broker confirmation.

## Shared versus concrete workers

`shared/workers` may contain:

- Abstract worker contracts.
- Generic claim-loop helpers.
- Generic outbox dispatcher base.
- Generic inbox consumer base.
- Generic inbox processor base.
- Worker runner infrastructure.
- Worker registry protocol/contract.

Module-specific workers belong in:

```text
src/modules/<module>/infra/workers/
```

For `agent`, expected concrete files include:

```text
src/modules/agent/infra/workers/outbox_dispatcher.py
src/modules/agent/infra/workers/inbox_consumer.py
src/modules/agent/infra/workers/inbox_processor.py
src/modules/agent/infra/workers/registry.py
```

A central runner may discover registries. It must not contain event handlers, routing keys, queue names, module-specific repositories, or business decisions.

## Event envelope requirements

Use a stable envelope for inter-module messaging:

- `event_id`
- `event_type`
- `event_version`
- `occurred_at`
- `producer`
- `aggregate_type`
- `aggregate_id`
- `routing_key`
- `payload`
- `metadata`
- `correlation_id`
- `causation_id`
- `idempotency_key`

Version events explicitly. Consumers must reject or dead-letter incompatible versions according to the active compatibility policy.

## Idempotency rules

Every event must have a deterministic idempotency key appropriate to the operation. Duplicate consumption must not produce duplicate state changes.

Implement idempotency at the durable boundary:

- Outbox uniqueness on `idempotency_key` for produced effects.
- Inbox uniqueness on message/event identity or consumer-specific idempotency key.
- Handler-level protection for state changes that may be retried.

Tests must prove duplicate delivery is safe.

## Retry and dead-letter rules

Use explicit statuses such as `pending`, `processing`, `published`, `processed`, `retryable`, `dead`, or the statuses defined by the active spec. Do not use ambiguous booleans as the primary state machine.

On transient failure:

- Increment attempts.
- Store error details.
- Set `available_at` for backoff.
- Return to `retryable` when attempts remain.

On terminal or incompatible failure:

- Mark dead.
- Preserve payload and metadata for audit.
- Route or expose to a dead-letter policy if RabbitMQ topology requires it.

## Locking and concurrency

Claims must be concurrency-safe. Prefer database-level row claiming with `FOR UPDATE SKIP LOCKED` or the repository's equivalent pattern. Two workers must not claim the same record. Tests should run concurrent claim attempts when the spec requires it.

## RabbitMQ topology

Document and test topology:

- Exchanges.
- Queues.
- Routing keys.
- Bindings.
- Dead-letter exchange/queue policy.
- Publisher confirms.
- Consumer ack/nack behavior.

Do not route by guessing the first segment of `event_type` unless the active spec explicitly preserves that temporarily. Prefer explicit routing keys and module registries.

## Required validation focus

Run or add tests for:

- Outbox claim and publish transitions.
- Publisher confirm success/failure.
- Inbox durable persistence before ack.
- Inbox processor idempotency.
- Duplicate delivery.
- Retry backoff.
- Dead-letter behavior.
- Concurrent claims.
- Worker registry discovery without domain leakage in root/shared workers.

## Forbidden shortcuts

- No in-memory-only event bus for state-changing integration.
- No direct calls to another module's repository from a handler.
- No broker ack before Inbox commit.
- No published status without broker confirm.
- No global worker with business event switch/case logic.
- No queue topology hard-coded in unrelated modules.
