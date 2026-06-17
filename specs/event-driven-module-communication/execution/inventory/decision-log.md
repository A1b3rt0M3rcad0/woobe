# Decision Log

## ADR 000 — comunicação cross-module por eventos transacionais

**Status:** accepted
**Data:** 2026-06-16
**Spec:** `000-adr-transactional-event-driven-module-communication.md`

### Decisão

1. Agent→Tool é chamada síncrona interna (Tool pertence ao bounded context agent).
2. Agent→Metering e Agent→Observability são integrações assíncronas obrigatórias via Outbox/Inbox.
3. Imports, repositories, models, ou Unit of Work de outro módulo são proibidos para alterar estado cross-module.
4. Consistência eventual para projeções e métricas.
5. O fluxo cross-module obrigatório é: estado local + Outbox (mesma transação) → dispatcher → RabbitMQ → consumer → Inbox + ACK → processor → caso de uso consumidor + estado local + Inbox processed (mesma transação).

### Evidências

- Branch: `development_event-driven-module-communication` — verified
- Baseline SHA `cd8d5867967fea25ea170bd88ebc9a461ed16c09` is ancestor of HEAD — verified
- Working tree: clean
- Cross-module import scan: no internal imports from agent into other modules found
- MeteringUsageRecorder, ObservabilityTraceRecorder, AgentToolExecutor: adapters internos do módulo agent
