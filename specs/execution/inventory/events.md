# Current event catalog

- Agent domain event definitions live in `src/modules/agent/domain/events.py`.
- Every integration event carries `event_type`, version, routing_key, idempotency key and correlation ID.
- Agent execution emits requested, started, LLM completed, tool completed, fallback, completed, failed and cancelled events.
- Agent configuration emits agent, credential, tool and release mutation events.
- `src/modules/agent/infra/messaging/event_mappers.py` maps domain events to OutboxEvent records.
- Repeatable mutation events scope idempotency to the concrete operation occurrence.
- Execution event idempotency is scoped to trace and call occurrence.
- RabbitMQ envelopes preserve event ID, routing key, correlation and causation metadata.
- InboxEvent records are created before handler dispatch and acknowledge only after persistence.
- Observability consumers project agent execution events into traces and trace events.
- Metering consumers project completed usage events into usage records.
- Billing consumers project billable usage from canonical integration events.
- Shared inbox and outbox models live in `src/shared/infra/database/`.
- Worker dispatch is coordinated through `src/shared/workers/`.
- Invalid envelopes are rejected rather than receiving fabricated identifiers.
- Event versions use the `.v1` contract suffix where applicable.
- Dead-letter and retry state is persisted with attempts and availability timestamps.
