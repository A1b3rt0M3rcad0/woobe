# Migration Risk Register

Generated: 2026-06-13
Spec: 009-create-migration-risk-register
Sources: specs 003-008 inventories (files.md, imports.md, database-ownership.md, routes.md, events.md, workers.md)
Commands executed: consolidated from inventory detection commands in specs 003-008

## Risk Register

| ID | Description | Severity | Probability | Evidence | Affected Specs | Mitigation | Unblock/Close Condition |
|---|---|---|---|---|---|---|---|
| R-001 | AskJobWorker assembles UoW spanning 5 modules (ai, knowledge, runtime, metering, observability) | critical | certain | `src/modules/runtime/infra/ask_job_worker.py:64-74` — single `PostgresUnitOfWork(session_factory)` coordinates repositories from 5 modules | 040-045, 074, 085 | After consolidation into agent, ai/knowledge/runtime become internal; metering and observability must be communicated via Outbox/Inbox events | UoW coordinates only agent-internal repositories; metering/observability interactions replaced by Outbox event publication |
| R-002 | ask_use_case.py imports 5 external modules directly (ai, knowledge, metering, observability, tools) | critical | certain | `src/modules/runtime/service/ask_use_case.py:13-47` — 28 imports from ai, 8 from knowledge, 7 from metering, 8 from observability, 8 from tools | 040-045, 070-085 | ai/knowledge/runtime merge into agent; metering/observability replace with Outbox events; tools replace with public contract or Inbox | All cross-module imports eliminated: ai/knowledge/runtime internal to agent; metering/observability via events; tools via public contract |
| R-003 | ask_agent_stream_service.py duplicates cross-module pattern of ask_use_case.py | critical | certain | `src/modules/runtime/service/ask_agent_stream_service.py:15-73` — imports from ai, knowledge, metering, observability, tools | 040-045, 070-085 | Same mitigation as R-002; both files merge into agent | Both files have zero cross-module imports after migration |
| R-004 | InboxConsumer routing broken for 19/27 event_types | critical | certain | `src/shared/workers/inbox_consumer.py:10-11` — `_module_for_event_type()` splits on first `.`; events like `user.created` route to non-existent module `user` | 100-109 | Standardize event_types with module prefix (`<module>.<aggregate>.<action>`) or replace routing with registry/lookup table | All event_types routable; no events silently dropped |
| R-005 | InboxConsumerWorker silently discards events when module import fails | critical | certain | `src/shared/workers/inbox_consumer.py:39-40` — ImportError/AttributeError caught and ignored without logging | 050-055, 100-109 | Add error logging and dead-letter handling; refactor to registry-based routing | No event silently lost; failed events logged and sent to DLQ |
| R-006 | Runtime directly produces metering-domain events (`usage_event.recorded`) | high | certain | `src/modules/runtime/service/ask_use_case.py:928`, `src/modules/runtime/service/ask_agent_stream_service.py:1062` | 040-045, 070-085 | Runtime (agent) should publish its own domain event (e.g., `agent.ask.completed`); metering consumes and records usage internally | Agent module publishes only agent-domain events; metering derives usage from its own Inbox processing |
| R-007 | Dispatcher handler keys do not match actual event_types produced | high | certain | `src/workers/dispatcher.py:35-39` — registers `identity.organization_created` but actual event is `organization.created`; 4/5 handlers never fire | 100-109 | Align handler keys with real event_types or remove global dispatcher in favor of per-module handlers | Dispatcher removed; all handlers in owning module respond to correct event_types |
| R-008 | Runner imports AskJobWorker directly from `modules.runtime.infra` | high | certain | `src/workers/runner.py:13` — `from modules.runtime.infra.ask_job_worker import AskJobWorker` | 054, 063 | Move to worker registry pattern; runner discovers workers via module registries | Runner has zero direct imports from any module's internal infra |
| R-009 | Shared workers hard-code module list (MODULES constant) | high | certain | `src/shared/workers/outbox_publisher.py:12-15`, `src/shared/workers/inbox_dispatcher.py:14-17` — hardcoded list of 9 modules | 050-063 | Replace with declarative registry per module; shared workers discover modules dynamically from registries | MODULES constant removed; shared workers use registry pattern |
| R-010 | Business event handlers located in global `src/workers/dispatcher.py` | high | certain | `src/workers/dispatcher.py:8-30` — 5 handlers for identity, core, ai, knowledge, metering events | 061, 062, 080-085 | Move handlers to owning module's `infra/workers/`; each module registers its own handlers | `src/workers/dispatcher.py` deleted; handlers in `src/modules/<module>/infra/workers/` |
| R-011 | 33 cross-module physical ForeignKeys violate final architecture | high | certain | `src/modules/*/infra/models.py` — ForeignKey() references to core.projects.id, identity.users.id, ai.agents.id across 8 modules | 134 | Expand-migrate-contract: add opaque UUID columns, migrate data, drop FK constraints | Zero ForeignKey() between distinct module schemas |
| R-012 | Single global queue `projectrai.inbox` with `#` binding | high | certain | `src/shared/workers/inbox_consumer.py:16,24` — all events compete in one queue with no isolation | 050-055, 106 | Migrate to per-module queues with specific routing key bindings | Each module has its own queue bound to relevant event routing keys |
| R-013 | AskJobWorker does not inherit BaseWorker | medium | certain | `src/modules/runtime/infra/ask_job_worker.py:35` — class has no parent class | 085 | Align with BaseWorker contract or new worker interface | All concrete workers implement BaseWorker (or successor) contract |
| R-014 | InboxConsumer uses dynamic importlib to load module internals | medium | certain | `src/shared/workers/inbox_consumer.py:37` — `importlib.import_module(f"modules.{module}.infra.models")` | 050-055 | Replace with registry that provides InboxEventModel references without dynamic import of internals | No dynamic import of module internals in shared layer |
| R-015 | No event version suffix convention enforced | medium | likely | All events use `event_version=1` default; no `.v1` in event_type string; field exists but unused | 102-109 | Define and enforce versioning policy; add schema_version to envelope | Versioning policy documented and enforced by architecture tests |
| R-016 | Event envelope missing fields vs best practice | medium | certain | Published envelope lacks timestamp, producer_module, idempotency_key, schema_version, trace_id (`src/shared/workers/outbox_publisher.py:47-56`) | 102-109 | Extend envelope to include missing fields | Envelope includes timestamp, producer_module, idempotency_key, schema_version |
| R-017 | No idempotency_key or unique constraint for inbox deduplication | medium | likely | Inbox has `outbox_origin_id` but no unique constraint visible in base model definition | 103, 125 | Add unique constraint on (event_type, outbox_origin_id) or dedicated idempotency_key column with unique index | Idempotency enforced by DB constraint; duplicate messages rejected |
| R-018 | 44 legacy routes need simultaneous shims during migration | medium | certain | 25 `/ai/*` + 12 `/knowledge/*` + 7 `/runtime/*` routes (`specs/execution/inventory/routes.md`) | 130-131 | Create redirect/shim routers with Deprecation header; test both old and new paths | Shims tested and active; old paths return deprecation header |
| R-019 | Three separate Outbox/Inbox table pairs in ai, knowledge, runtime must merge into single agent pair | medium | certain | `ai.outbox_events`, `ai.inbox_events`, `knowledge.outbox_events`, `knowledge.inbox_events`, `runtime.outbox_events`, `runtime.inbox_events` | 070-076 | Expand-migrate-contract: create `agent.outbox_events`/`agent.inbox_events`, migrate pending events, deprecate legacy tables | Single `agent.outbox_events` and `agent.inbox_events` active; legacy tables empty and removed |
| R-020 | Alembic env.py hardcodes legacy module imports | low | certain | `migrations/env.py:15-23` — imports all modules' `infra.models` including ai, knowledge, runtime | 134 | Add agent module import; remove legacy imports after full migration | `migrations/env.py` imports `modules.agent.infra.models` only; no ai/knowledge/runtime imports |
| R-021 | Dynamic event_type in billing (`payment_event.{type}`) | medium | certain | `src/modules/billing/service/use_cases.py:179` — unbounded event_type namespace | 102-109 | Define closed enum of billing payment event subtypes or use structured routing | Billing event_types statically catalogable and routable |
| R-022 | ask_agent_composer.py imports repositories from 5 modules | high | certain | `src/modules/runtime/application/composers/ask_agent_composer.py:3-26` — imports from ai, knowledge, runtime, metering, observability | 040-045, 074 | Merge ai/knowledge/runtime repos into agent; metering/observability replaced by event publication | Composer imports only from agent module internals |
| R-023 | observability.traces.session_id references runtime.sessions.id (cross-module after consolidation) | medium | certain | `src/modules/observability/infra/models.py:21` — ForeignKey to runtime.sessions.id; remains cross-module even after agent consolidation (observability != agent) | 134 | Remove FK; store session_id as opaque UUID reference; observability receives session data via events | FK removed; session_id stored as plain UUID without constraint |
| R-024 | No worker tests exist in repository | medium | certain | `specs/execution/inventory/workers.md` — "Não existe nenhum teste unitário ou de integração para workers no repositório atual" | 120-129 | Create worker unit and integration tests as part of agent worker specs | Worker tests exist and pass for all concrete workers |
| R-025 | `tests/unit/test_core` and `tests/unit/test_identity` missing `__init__.py` | low | certain | Pre-existing pytest collection errors (10 errors) | N/A (pre-existing) | Add missing `__init__.py` files | pytest collection passes without errors from these directories |
| R-026 | ruff reports 29 pre-existing errors (F401, F821, F841) in legacy modules | low | certain | `ruff check src tests` output from spec execution environment | N/A (pre-existing) | Fix lint errors in owning modules during or after migration | ruff exits with 0 errors |

## Summary

| Severity | Count |
|---|---|
| Critical | 5 |
| High | 7 |
| Medium | 11 |
| Low | 3 |
| **Total** | **26** |

## Critical risks requiring resolution before physical migration

1. **R-001** (UoW cross-module) — blocks safe execution; must be resolved by spec 074.
2. **R-002 / R-003** (cross-module imports in ask flows) — blocks clean agent module; resolved by specs 040-045.
3. **R-004 / R-005** (broken inbox routing) — blocks event-driven communication; resolved by specs 100-109.

## Risk resolution timeline

| Phase | Specs | Risks resolved |
|---|---|---|
| Agent skeleton + migration | 010-045 | R-002, R-003, R-022 (cross-module imports become intra-module) |
| Worker refactoring | 050-063 | R-008, R-009, R-010, R-012, R-013, R-014 |
| Agent Outbox/Inbox/UoW | 070-085 | R-001, R-006, R-019, R-024 |
| Event standardization | 100-109 | R-004, R-005, R-007, R-015, R-016, R-017, R-021 |
| Bootstrap/config/migrations | 130-134 | R-011, R-018, R-020, R-023 |
| Final cleanup | 150-154 | R-025, R-026 (if addressed) |
