# Worker and Registry Inventory

**Date:** 2026-06-14
**Branch:** project-rai-playground_module-architecture-standardization
**SHA:** bd9aa35

## Notes
- Generated during spec 017 execution.
- `find` (Unix) and `rg` unavailable on Windows; substituted with `Get-ChildItem` and `Select-String`.

## Worker Files by Module

### agent — 4 concrete workers + registry
| File | Role |
|---|---|
| `src/modules/agent/infra/workers/__init__.py` | Module marker |
| `src/modules/agent/infra/workers/registry.py` | `AgentWorkerRegistry` + `register_agent_workers()` |
| `src/modules/agent/infra/workers/ask_job_worker.py` | `AskJobWorker` — polls pending jobs, delegates to `AskAgentUseCase` |
| `src/modules/agent/infra/workers/inbox_consumer.py` | `AgentInboxConsumerWorker` — consumes RabbitMQ, persists to Inbox |
| `src/modules/agent/infra/workers/inbox_processor.py` | `AgentInboxProcessorWorker` — claims pending Inbox events, routes to handlers |
| `src/modules/agent/infra/workers/outbox_dispatcher.py` | `AgentOutboxDispatcherWorker` — claims pending Outbox events, publishes to RabbitMQ |

### billing — registry stub only (no concrete workers)
| File | Role |
|---|---|
| `src/modules/billing/infra/workers/__init__.py` | Module marker |
| `src/modules/billing/infra/workers/registry.py` | `BillingWorkerRegistry` — empty registry, no workers registered |

### core — no workers directory
core has no `infra/workers/` directory at all.

### identity — registry stub only
| File | Role |
|---|---|
| `src/modules/identity/infra/workers/__init__.py` | Module marker |
| `src/modules/identity/infra/workers/registry.py` | `IdentityWorkerRegistry` — empty registry, no workers registered |

### metering — registry stub only
| File | Role |
|---|---|
| `src/modules/metering/infra/workers/__init__.py` | Module marker |
| `src/modules/metering/infra/workers/registry.py` | `MeteringWorkerRegistry` — empty registry, no workers registered |

### observability — registry stub only
| File | Role |
|---|---|
| `src/modules/observability/infra/workers/__init__.py` | Module marker |
| `src/modules/observability/infra/workers/registry.py` | `ObservabilityWorkerRegistry` — empty registry, no workers registered |

### tools — registry stub only
| File | Role |
|---|---|
| `src/modules/tools/infra/workers/__init__.py` | Module marker |
| `src/modules/tools/infra/workers/registry.py` | `ToolsWorkerRegistry` — empty registry, no workers registered |

## Shared Worker Infrastructure

| File | Role |
|---|---|
| `src/shared/workers/contracts.py` | `WorkerProtocol` and `WorkerRegistryProtocol` (Protocol classes) |
| `src/shared/workers/base_worker.py` | `BaseWorker` (ABC — base for all workers) |
| `src/shared/workers/runner.py` | `WorkerRunner` — accepts list/registries, runs `run_once()` or `run_loop()` |
| `src/shared/workers/inbox_consumer.py` | Shared inbox consumer (used by agent's InboxConsumerWorker) |
| `src/shared/workers/inbox_consumer_base.py` | Base class for inbox consumers |
| `src/shared/workers/inbox_dispatcher.py` | Shared inbox dispatcher |
| `src/shared/workers/inbox_processor_base.py` | Base class for inbox processors |
| `src/shared/workers/outbox_dispatcher_base.py` | Base class for outbox dispatchers |
| `src/shared/workers/outbox_publisher.py` | Shared outbox publisher |

## Registry Classes

| Module | Registry Class | Implements WorkerRegistryProtocol? | Has Workers? |
|---|---|---|---|
| agent | `AgentWorkerRegistry` | Yes (asserted in code) | Yes (4 workers) |
| billing | `BillingWorkerRegistry` | Yes (asserted) | No (stub) |
| identity | `IdentityWorkerRegistry` | Yes (asserted) | No (stub) |
| metering | `MeteringWorkerRegistry` | Yes (asserted) | No (stub) |
| observability | `ObservabilityWorkerRegistry` | Yes (asserted) | No (stub) |
| tools | `ToolsWorkerRegistry` | Yes (asserted) | No (stub) |
| core | _(none)_ | No | No |

## Agent Worker Registration

The `register_agent_workers()` function in `agent/infra/workers/registry.py`:
1. Creates `AgentRabbitMQPublisher`
2. Creates and registers `AgentOutboxDispatcherWorker`
3. Creates and registers `AgentInboxConsumerWorker`
4. Creates `AgentInboxEventRouter` (empty — no handlers registered yet)
5. Creates and registers `AgentInboxProcessorWorker`

## Module __init__.py Exports

All modules (except core) export their registry from `__init__.py`:
```python
from modules.{module}.infra.workers import registry
```

This provides `registry.{Module}WorkerRegistry` for bootstrapping.

## WorkerRunner Wiring

`shared/workers/runner.py` defines:
- `WorkerRunner(workers)` — runs a list of workers
- `WorkerRunner.from_registries(registries)` — collects workers from multiple registries
- `run_once()` — runs all workers once
- `run_loop(interval)` — runs workers in a loop with signal handling

## Gaps and Risks

| Gap/Risk | Command needed | Severity |
|---|---|---|
| Only agent has concrete workers (4); billing, identity, metering, observability, tools have empty registry stubs | Create per-module workers (spec 037-087) | high |
| core has no workers directory at all | Create core module workers (spec 047) | high |
| `AgentInboxEventRouter` is instantiated with no registered handlers | Register handlers (spec 027) | medium |
| `AskJobWorker` imports from `modules.metering` and `modules.observability` — cross-module dependency | Refactor to messaging (spec 027) | high |
| No central WorkerRunner integration in bootstrap | Wire registries to runner (spec 095) | medium |
| All registry classes are almost identical (boilerplate) | Possibly share via base class (spec 095) | low |

## Acceptance Criteria

- [x] `workers.md` exists and is not empty
- [x] SHA of inventory registered: `bd9aa35`
- [x] Gaps have explicit commands and risks
- [x] Worker files classified per module
- [x] Registry classes catalogued
- [x] Shared worker infrastructure documented
- [x] Cross-module import risk identified in AskJobWorker
