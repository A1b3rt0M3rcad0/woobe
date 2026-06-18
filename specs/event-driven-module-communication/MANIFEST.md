# MANIFEST — Event-Driven Module Communication

- Repository: `A1b3rt0M3rcad0/ProjectRAI`
- Baseline: `development` @ `cd8d5867967fea25ea170bd88ebc9a461ed16c09`
- Execution branch: `development_event-driven-module-communication`
- Numbered specs: 20

## Ordem

1. `000-adr-transactional-event-driven-module-communication.md` — ADR — comunicação cross-module por eventos transacionais
2. `001-inventory-cross-module-dependencies-and-flows.md` — Inventário de imports, writes, eventos, workers e FKs
3. `002-define-target-event-flow-and-subscription-matrix.md` — Matriz alvo de eventos, ownership e subscriptions
4. `003-add-characterization-and-architecture-guards.md` — Testes de caracterização e guards arquiteturais
5. `004-standardize-integration-event-envelope.md` — Envelope canônico de IntegrationEvent
6. `005-standardize-outbox-inbox-persistence.md` — Persistência canônica de Outbox e Inbox
7. `006-fix-worker-lifecycle-and-rabbitmq-topology.md` — Lifecycle de workers e topologia RabbitMQ
8. `007-fix-agent-outbox-and-event-catalog.md` — Outbox e catálogo de eventos do agent
9. `008-refactor-synchronous-agent-execution.md` — Execução síncrona do agent em fases transacionais
10. `009-refactor-streaming-and-ask-jobs.md` — Streaming e AskJobs no mesmo orchestrator
11. `010-stabilize-internal-tool-execution-and-events.md` — Tool interna: composição, secrets e eventos
12. `011-implement-metering-rabbit-consumer-and-inbox.md` — Consumer RabbitMQ e Inbox do metering
13. `012-implement-metering-dispatcher-and-idempotent-use-cases.md` — Dispatcher e casos de uso idempotentes do metering
14. `013-implement-observability-rabbit-consumer-and-inbox.md` — Consumer RabbitMQ e Inbox do observability
15. `014-implement-observability-idempotent-projection.md` — Projeção idempotente de observability
16. `015-register-workers-retries-dlq-and-replay.md` — Registries, retries, DLQ, locks e replay
17. `016-fix-identity-core-billing-communication.md` — Identity, Core e Billing: remover integração de fachada
18. `017-remove-cross-module-foreign-keys.md` — Remover Foreign Keys cross-module
19. `018-run-end-to-end-failure-and-atomicity-tests.md` — E2E de atomicidade, falhas, ordering e replay
20. `019-cutover-remove-adapters-and-final-validation.md` — Cutover, remoção de adapters e validação final

## Gates

- 000–002: decisão e inventário.
- 003–006: guards, contrato e runtime de mensageria.
- 007–010: producer agent e Tool interna.
- 011–015: consumers metering/observability.
- 016–017: demais módulos e banco.
- 018–019: E2E e cutover.

Não avançar com prerequisite pendente, teste obrigatório falhando, backlog desconhecido ou rollback não testado.