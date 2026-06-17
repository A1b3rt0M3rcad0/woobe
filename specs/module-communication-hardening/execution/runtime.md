# Execution Runtime

## Suite

`specs/module-communication-hardening`

## Branch

`development_event-driven-module-communication`

## Baseline

`b4f5c9cc9d8a9d990e3ae330c036440d9843c2c8`

## Status

| Spec | Status |
|---|---|
| 000 | completed |
| 001 | completed |
| 002 | completed |
| 003 | completed |
| 004 | completed |
| 005 | completed |
| 006 | completed |
| 007 | completed |
| 008 | pending |
| 009 | pending |

## Specs executadas

### 001 — Corrigir async/await e fronteiras transacionais do Agent

**Status:** completed
**Tipo:** agent/application
**Data:** 2026-06-16
**Scope:** module-communication-hardening

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` (verify branch) | 0 |
| `git status --short` | 0 |
| `Get-ChildItem -Recurse -Filter "*.py" -Path src, tests | Select-String -Pattern "MeteringUsageRecorder|ObservabilityTraceRecorder|_legacy_mode|agent\\.#|outbox\\.write\\(|_do_save_assistant_message"` | 0 |
| `Get-ChildItem -Recurse -Filter "*.py" -Path src, tests | Select-String -Pattern "agent\\.execution\\.(started|llm_completed|tool_completed)\\.v1|event_type=.*\\.created"` | 0 |

**Files changed:**
- `src/modules/agent/application/use_cases/ask_use_case.py` — added `await` before 5 `outbox.write()` calls, added `await` before `json_model.ainvoke()`, replaced `except Exception: pass` with `logger.warning` in session update failure (×2)
- `src/modules/agent/application/use_cases/ask_agent_stream_service.py` — added `await` before 4 `outbox.write()` calls
- `src/modules/agent/application/use_cases/runtime_use_cases.py` — added `await` before `self._outbox.write()`
- `tests/integration/agent/test_spec009_stream_job_orchestrator.py` — changed `MagicMock()` to `AsyncMock()` for outbox to support `await`
- `tests/architecture/test_characterization_async_boundaries.py` — cleared KNOWN_VIOLATIONS (all fixed)
- `execution/runtime.md` — runtime updated

**Communication paths hardened:**
- 10 `outbox.write()` calls now correctly awaited across 3 files (ask_use_case.py ×5, ask_agent_stream_service.py ×4, runtime_use_cases.py ×1)
- `json_model.ainvoke()` now awaited in ask_use_case.py _execute_llm
- Session update failures now logged instead of silently swallowed (×2 locations)

**Validation commands:**
| Comando | Exit code |
|---|---|
| `python -m ruff check src/modules/agent/application/use_cases/ask_use_case.py src/modules/agent/application/use_cases/ask_agent_stream_service.py src/modules/agent/application/use_cases/runtime_use_cases.py tests/integration/agent/test_spec009_stream_job_orchestrator.py tests/architecture/test_characterization_async_boundaries.py` | 0 (7 pre-existing unused-import warnings in test file) |
| `python -m pytest tests/architecture/test_characterization_async_boundaries.py tests/architecture/test_characterization_legacy_mode.py -v` | 0 (4 passed) |
| `python -m pytest tests/integration/agent/test_ask_execution_phases.py -q` | 0 (7 passed) |
| `python -m pytest tests/integration/agent/test_spec009_stream_job_orchestrator.py -q` | 0 (9 passed) |
| `python -W error::RuntimeWarning -m pytest tests/integration/agent -q` | 1 (24 passed, 29 pre-existing async failures — zero RuntimeWarning) |

**Known defects resolved:**
- D001: All missing `await` on `outbox.write()` fixed
- D003: `_legacy_mode` patterns documented but not removed (corrective spec 001 — kept for backward compat in this spec)
- D004: `_do_save_assistant_message` now correctly awaits `outbox.write()` inside

**Decisões:**
- `_legacy_mode` and `_do_save_assistant_message` legacy patterns remain for backward compatibility. Characterization test `test_characterization_legacy_mode.py` continues to track them.
- `_execute_legacy` path kept intact — its removal belongs to spec 002.
- `except Exception: pass` in session update paths replaced with `logger.warning` to preserve observability without breaking existing behavior.

**Riscos:**
- `_legacy_mode` still active — legacy code path preserved.
- Characterization tests D002–D006 still active.

### 002 — Remover o caminho legado cross-module do AskJob

**Status:** completed
**Tipo:** agent/workers
**Data:** 2026-06-16
**Scope:** module-communication-hardening

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` (verify branch) | 0 |
| `git status --short` | 0 |
| `Select-String -Path "src/**/*.py", "tests/**/*.py" -Pattern "MeteringUsageRecorder|ObservabilityTraceRecorder|_execute_legacy|_legacy_mode"` | 0 |

**Files changed:**
- `src/modules/agent/infra/adapters/metering_usage_recorder.py` — DELETED
- `src/modules/agent/infra/adapters/observability_trace_recorder.py` — DELETED
- `src/modules/agent/domain/ports/trace_recorder.py` — DELETED
- `src/modules/agent/domain/ports/usage_recorder.py` — DELETED
- `src/modules/agent/application/use_cases/ask_use_case.py` — removed `_legacy_mode` flag, `_execute_legacy`, `_load_agent_legacy`, `_load_rag_context_legacy`, 10 legacy constructor params
- `src/modules/agent/infra/workers/ask_job_worker.py` — migrated to phased path (uses `AskAgentUseCase` with `session_factory`, `llm_factory`, `encryption_key`)
- `tests/integration/agent/test_ask_execution_phases.py` — removed legacy mode tests, updated to reflect phased-only execution
- `tests/architecture/test_characterization_legacy_mode.py` — cleared KNOWN_LEGACY_PATTERNS; now scans for zero legacy adapter patterns
- `tests/architecture/test_characterization_tool_wiring.py` — cleared KNOWN_ADAPTER_IMPORTS/KNOWN_ADAPTER_CLASSES (all resolved)
- `execution/runtime.md` — runtime updated

**Communication paths hardened:**
- Removed cross-module direct writes: Agent → Metering (MeteringUsageRecorder), Agent → Observability (ObservabilityTraceRecorder)
- Removed 4 dynamic cross-module imports (importlib.import_module to metering/observability)
- Removed legacy mode feature flag (`_legacy_mode`)
- Removed legacy code paths (`_execute_legacy`, `_load_agent_legacy`, `_load_rag_context_legacy`)
- AskJobWorker now uses same phased execution path as HTTP/stream endpoints

**Validation commands:**
| Comando | Exit code |
|---|---|
| `python -m ruff check src/modules/agent/application/use_cases/ask_use_case.py src/modules/agent/infra/workers/ask_job_worker.py tests/integration/agent/test_ask_execution_phases.py tests/architecture/test_characterization_legacy_mode.py tests/architecture/test_characterization_tool_wiring.py` | 0 |
| `Select-String "MeteringUsageRecorder|ObservabilityTraceRecorder|_execute_legacy|_legacy_mode" src tests` | 0 (zero matches) |
| `python -m pytest tests/integration/agent/test_ask_execution_phases.py tests/integration/agent/test_spec009_stream_job_orchestrator.py -q` | 0 (15 passed) |
| `python -m pytest tests/architecture/test_event_dynamic_imports.py -q` | 0 (2 passed) |
| `python -m pytest tests/architecture/test_characterization_legacy_mode.py tests/architecture/test_characterization_tool_wiring.py tests/architecture/test_characterization_async_boundaries.py -v` | 0 (6 passed) |

**Known defects resolved:**
- D002: MeteringUsageRecorder/ObservabilityTraceRecorder adapters removed; ask_job_worker.py no longer uses them.
- D003: `_legacy_mode` flag removed entirely from ask_use_case.py.

**Decisões:**
- AskJobWorker now initialized with minimal params (session_factory, llm_factory, encryption_key) — same pattern as HTTP composer.
- Deleted adapters and ports are never coming back — Outbox/Inbox the only cross-module path.
- `_do_save_assistant_message` retained as a valid helper method (its internal `outbox.write()` was already awaited in spec 001).

**Riscos:**
- D005, D006 still active (unversioned events, agent.# self-subscription).
- Pre-existing async test failures (pytest-asyncio) unchanged.

### 003 — Completar eventos do Agent e corrigir idempotência

**Status:** completed
**Tipo:** messaging/domain
**Data:** 2026-06-16
**Scope:** module-communication-hardening

**Files changed:**
- `src/modules/agent/domain/events.py` — added AgentExecutionStartedV1, AgentExecutionLLMCompletedV1, AgentExecutionToolCompletedV1 event classes
- `src/modules/agent/application/use_cases/ask_use_case.py` — emit started.v1 in _prepare, llm_completed.v1 + tool_completed.v1 in _finalize
- `src/modules/agent/application/use_cases/ask_agent_stream_service.py` — emit started.v1 in prepare UoW, llm_completed.v1 + tool_completed.v1 in finalize UoW
- `src/modules/agent/infra/workers/inbox_consumer.py` — removed `agent.#` self-subscription (replaced with empty routing keys)
- `src/modules/billing/application/use_cases/billing_use_cases.py` — versioned events: plan.created.v1, customer.created.v1, subscription.created.v1
- `src/modules/core/application/use_cases/create_project_use_case.py` — versioned: project.created.v1
- `src/modules/core/application/use_cases/create_api_key_use_case.py` — versioned: api_key.created.v1
- `src/modules/core/application/use_cases/update_project_use_case.py` — versioned: project.updated.v1
- `src/modules/identity/application/use_cases/identity_use_cases.py` — versioned: user.created.v1, organization.created.v1, organization.member_added.v1, organization.updated.v1, organization.invite_created.v1
- `src/modules/observability/application/use_cases/observability_use_cases.py` — versioned: trace.created.v1, trace_event.created.v1
- `src/modules/metering/application/use_cases/metering_use_cases.py` — versioned: usage_event.recorded.v1
- `tests/architecture/test_characterization_unversioned_events.py` — cleared KNOWN_UNVERSIONED (all resolved)
- `tests/architecture/test_characterization_subscriptions.py` — removed agent.# from KNOWN_SELF_SUBSCRIBERS; verifies zero new self-subscribers
- `execution/runtime.md` — runtime updated

**Communication paths hardened:**
- 3 new event types added to agent domain events (started, llm_completed, tool_completed)
- Agent now emits all 7 agent.execution.*.v1 events across its lifecycle
- 14 unversioned event_type strings across 5 modules versioned with .v1 suffix
- agent.# self-subscription removed — agent no longer consumes its own events via glob pattern

**Public contracts, events, Outbox, Inbox, workers, handlers, retries, timeouts, error contracts changed:**
- New event classes: AgentExecutionStartedV1, AgentExecutionLLMCompletedV1, AgentExecutionToolCompletedV1
- Agent inbox consumer routing keys changed: ["agent.#"] → []

**Known defects resolved:**
- D005: All billing/core/identity/observability/metering events now versioned (.v1)
- D006: agent.# self-subscription removed

**Validation commands:**
| Comando | Exit code |
|---|---|
| `python -m ruff check src/modules/agent/domain/events.py src/modules/agent/application/use_cases/ask_use_case.py src/modules/agent/application/use_cases/ask_agent_stream_service.py src/modules/agent/infra/workers/inbox_consumer.py` | 0 |
| `python -m pytest tests/unit/agent/test_agent_outbox_writer.py -q` | 0 (20 passed) |
| `python -m pytest tests/contract/events -q` | 0 (19 passed) |
| `python -m pytest tests/architecture/test_characterization_unversioned_events.py tests/architecture/test_characterization_subscriptions.py -v` | 0 (5 passed) |

**Decisões:**
- Intermediate events (started, llm_completed, tool_completed) emitted in existing UoWs (started in _prepare, llm_completed/tool_completed in _finalize) to avoid creating extra short UoWs.
- billing/core/identity inbox consumer files with `.#` patterns preserved (deactivated in registry since spec 016). Kept as known in characterization test.

**Riscos:**
- Pre-existing async test failures (pytest-asyncio) unchanged.

### 004 — Corrigir projeção idempotente do Metering

**Status:** completed
**Tipo:** metering
**Data:** 2026-06-16
**Scope:** module-communication-hardening

**Files changed:**
- `src/modules/metering/infra/messaging/inbox_handlers.py` — added `handle_noop` handler, renamed `handle_execution_requested` to `handle_execution_started`, mapped `requested.v1` to no-op, `started.v1` to log-counting
- `tests/integration/metering/test_spec012_metering_dispatcher.py` — updated import and tests to reflect handler rename and no-op semantics
- `execution/runtime.md` — runtime updated

**Communication paths hardened:**
- Metering no longer double-counts executions: `requested.v1` is no-op, `started.v1` counts the execution
- `handle_noop` used for events that should not trigger business effects (requested, completed, failed)

**Validation commands:**
| Comando | Exit code |
|---|---|
| `python -m ruff check src/modules/metering/infra/messaging/inbox_handlers.py tests/integration/metering/test_spec012_metering_dispatcher.py` | 0 |
| `python -m pytest tests/integration/metering -q` | 0 (31 passed) |
| `python -m pytest tests/contract/events -q` | 0 (19 passed) |

**Decisões:**
- `requested.v1` → no-op: execution is not counted until it actually starts
- `started.v1` → log: execution start is noted but metering data comes from `llm_completed.v1`
- Double-counting prevention: each event type maps to exactly one handler; no shared handlers

**Riscos:**
- Pre-existing async test failures (pytest-asyncio) unchanged.

### 000 — Reabrir o cutover e criar gates de regressão

**Status:** completed
**Tipo:** architecture/testing
**Data:** 2026-06-16
**Scope:** module-communication-hardening

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` (verify branch, adapted from spec's `development_module-communication-hardening` to actual `development_event-driven-module-communication`) | 0 |
| `git status --short` | 0 |
| `Get-ChildItem -Recurse -Filter "*.py" -Path src, tests | Select-String -Pattern "MeteringUsageRecorder|ObservabilityTraceRecorder|_legacy_mode|agent\\.#|outbox\\.write\\(|_do_save_assistant_message"` | 0 |
| `Get-ChildItem -Recurse -Filter "*.py" -Path src, tests | Select-String -Pattern "agent\\.execution\\.(started|llm_completed|tool_completed)\\.v1|event_type=.*\\.created"` | 0 |

**Files changed:**
- `execution/inventory/detection-spec-000.md` — detection evidence persisted
- `execution/inventory/known-defects.md` — defect matrix with 7 defects, test mappings, corrective spec references
- `tests/architecture/test_characterization_async_boundaries.py` — guard for missing `await` on `outbox.write()`
- `tests/architecture/test_characterization_tool_wiring.py` — guard for legacy adapter imports
- `tests/architecture/test_characterization_unversioned_events.py` — guard for unversioned events in non-agent modules
- `tests/architecture/test_characterization_legacy_mode.py` — guard for `_legacy_mode`/`_do_save_assistant_message`
- `tests/architecture/test_characterization_subscriptions.py` — guard for subscription gaps and self-subscriptions
- `execution/runtime.md` — runtime updated

**Communication paths hardened:**
- Nenhum — document-only and test-only spec. No production code changed.

**Public contracts, events, Outbox, Inbox, workers, handlers, retries, timeouts, error contracts changed:**
- Nenhum — no production code changed.

**Known defects documented:**
| ID | Defect | Corrective spec | Status |
|---|---|---|---|
| D001 | Missing `await` on `outbox.write()` (ask_use_case.py ×5, ask_agent_stream_service.py ×4) | 001 | resolved |
| D002 | MeteringUsageRecorder/ObservabilityTraceRecorder adapters still used by ask_job_worker.py | 002 | resolved |
| D003 | `_legacy_mode` flag still active | 001 | resolved |
| D004 | `_do_save_assistant_message` legacy direct-write | 001 | resolved |
| D005 | Unversioned events in billing/core/identity | 003 | resolved |
| D006 | `agent.#` self-subscription routing key | 003 | resolved |
| D007 | Metering/observability consumers missing 4 event types | 004, 005 | invalid (routing keys already present) |

**Validation commands:**
| Comando | Exit code |
|---|---|
| `python -m ruff check tests/architecture tests/integration/agent` | 0 (12 pre-existing warnings, none in new files) |
| `python -m pytest tests/architecture/test_characterization_async_boundaries.py tests/architecture/test_characterization_legacy_mode.py tests/architecture/test_characterization_subscriptions.py tests/architecture/test_characterization_unversioned_events.py tests/architecture/test_characterization_tool_wiring.py -v` | 0 (13 passed) |
| `python -m pytest tests/architecture -q` | 1 (717 passed, 86 pre-existing failures — all in pre-existing tests, unrelated to this spec) |
| `python -m pytest tests/integration/agent -q` | 1 (24 passed, 29 pre-existing async failures — pytest-asyncio plugin issue, pre-existing) |

**Decisões:**
- Branch check adapted: spec header says `development_module-communication-hardening` (typo), actual branch per suite files is `development_event-driven-module-communication`.
- Characterization tests use KNOWN_VIOLATIONS sets that document current defects. Tests pass because violations are expected.
- As hardening specs (001-009) fix each defect, the known-violation entries are removed.
- `_do_save_assistant_message` exists natively in `ask_use_case.py` — not a dynamic import pattern; detected as a legacy direct-write pattern.

**Riscos:**
- 7 known defects documented; 6 resolved (D001-D006), 1 invalid (D007).
- Characterization tests depend on KNOWN_VIOLATIONS sets remaining accurate as code changes.

### 005 — Corrigir projeção idempotente do Observability

**Status:** completed
**Tipo:** observability
**Data:** 2026-06-16
**Scope:** module-communication-hardening

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` (verify branch) | 0 |
| `git status --short` | 0 |
| `Select-String "MeteringUsageRecorder\|ObservabilityTraceRecorder\|_legacy_mode\|agent\.#\|outbox\.write\(\|_do_save_assistant_message" src tests` | 0 (legacy patterns in characterization tests) |
| `Select-String "agent\.execution\.(started\|llm_completed\|tool_completed)\.v1\|event_type=.*\.created" src tests` | 0 (versioned events present) |
| `Select-String "UUID\(int=0\)" src/modules/observability` | 0 (zero sentinel IDs remaining) |
| `Select-String "from modules\.(?!observability)" src/modules/observability` | 0 (zero cross-module reads) |

**Files changed:**
- `src/modules/observability/infra/messaging/inbox_handlers.py` — terminal state guard, deterministic TraceEvent ID via uuid5, idempotent upsert of Trace via `_get_or_create_trace`, mandatory field validation (project_id), removed `UUID(int=0)` sentinel values
- `tests/integration/observability/test_spec014_observability_projection.py` — added 16 new tests across 4 new classes: `TestTerminalStateProtection` (5 tests), `TestDeterministicEventIds` (5 tests), `TestOutOfOrderEvents` (2 tests), `TestNoSentinelIds` (4 tests)
- `specs/module-communication-hardening/execution/runtime.md` — runtime updated

**Communication paths hardened:**
- 6 inbox handlers now guard against terminal state regression
- 2 TraceEvent types (llm_call, tool_call) use deterministic IDs for idempotent replay
- All handlers validate mandatory `project_id` field
- `handle_trace_started` upgraded from always-create to upsert pattern via `_get_or_create_trace`
- Zero `UUID(int=0)` sentinel values in observability handlers

**Public contracts, events, Outbox, Inbox, workers, handlers, retries, timeouts, error contracts changed:**
- `_is_terminal_status()` helper added
- `_make_deterministic_event_id()` helper added (uuid5 with NAMESPACE_DNS)
- All 6 handlers: added project_id validation + terminal state guard
- `handle_llm_call` and `handle_tool_call`: TraceEvent now created with deterministic `id` instead of auto-generated uuid6

**Tests created or updated:**
- 16 new tests added to `test_spec014_observability_projection.py`
- `TestTerminalStateProtection`: completed after started, failed does not regress to completed, completed does not regress to failed, started skipped when terminal, llm_call skipped when terminal
- `TestDeterministicEventIds`: same trace+event produces same ID, different traces differ, different events differ, replay upsert
- `TestOutOfOrderEvents`: completed before started works, started after completed does not regress
- `TestNoSentinelIds`: project_id used correctly, missing project_id causes early return for started/completed/failed

**Validation commands:**
| Comando | Exit code |
|---|---|
| `python -m ruff check src/modules/observability/infra/messaging/inbox_handlers.py tests/integration/observability/test_spec014_observability_projection.py` | 0 |
| `python -m pytest tests/integration/observability -q` | 0 (48 passed) |
| `python -m pytest tests/contract/events -q` | 0 (19 passed) |

**Known defects resolved:**
- No observer from this spec, but D007 (metering/observability consumers missing event types) was already marked invalid in spec 000
- Sentinel IDs (UUID(int=0)) removed from all observability inbox handlers

**Decisões:**
- Deterministic event IDs (uuid5) chosen instead of explicit `source_event_id` column to avoid DB migration in this spec. The upsert behavior of `SQLAlchemyTraceEventRepository.save()` (upsert by PK) provides the same dedup guarantee.
- Terminal status set includes completed, failed, and cancelled. When a trace has reached any of these, all further events for that trace are skipped.
- Missing `project_id` causes early return (event skipped) instead of falling back to sentinel UUID.

**Riscos:**
- If `project_id` is genuinely missing from an event that should have it, the event is silently dropped (logged at INFO level). No exception propagates.
- Pre-existing async test failures (pytest-asyncio) unchanged.

### 006 — Corrigir Tool e remover self-subscription do Agent

**Status:** completed
**Tipo:** agent/tools/workers
**Data:** 2026-06-16
**Scope:** module-communication-hardening

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` (verify branch) | 0 |
| `git status --short` | 0 |
| `Select-String "MeteringUsageRecorder\|ObservabilityTraceRecorder\|_legacy_mode\|agent\.#\|outbox\.write\(\|_do_save_assistant_message" src tests` | 0 (legacy patterns only in characterization tests) |
| `Select-String "agent\.execution\.(started\|llm_completed\|tool_completed)\.v1\|event_type=.*\.created" src tests` | 0 (versioned events present) |

**Files changed:**
- `src/modules/agent/application/use_cases/ask_use_case.py` — added `tool_executor_factory: Callable[[UUID, dict], Awaitable[dict]]` param; `_execute_single_tool` uses factory when executor is unavailable
- `src/modules/agent/application/composers/ask_agent_composer.py` — creates per-execution tool factory opening its own AgentUnitOfWork, with SecretCipherAdapter + ToolSecretResolverAdapter + HttpToolExecutor; passes factory to AskAgentUseCase
- `src/modules/agent/application/use_cases/ask_agent_stream_service.py` — replaced stale `AgentToolExecutor(tool_repo)` with per-execution `_execute_tool` async closure that opens own UoW, includes secret resolution via ToolSecretResolverAdapter; removed `AgentToolExecutor` import
- `src/modules/agent/infra/workers/ask_job_worker.py` — added per-execution tool factory with SecretCipherAdapter + ToolSecretResolverAdapter + HttpToolExecutor; passes factory as `tool_executor_factory` to AskAgentUseCase
- `src/modules/agent/infra/workers/registry.py` — removed `AgentInboxConsumerWorker` and `AgentInboxProcessorWorker` registrations (dead code: empty routing keys, no handlers); removed unused imports
- `tests/architecture/test_event_self_subscriptions.py` — updated `test_agent_self_subscription_is_justified` to `test_agent_no_self_subscription`, verifying zero agent self-subscriptions remaining

**Communication paths hardened:**
- Tool execution in ask, stream, and job paths now uses per-execution sessions (no stale UoW reuse)
- Tool execution in stream includes secret resolution (was missing previously)
- Agent inbox consumer/processor removed (dead workers with empty routing keys and no handlers)
- Agent self-subscription (`agent.#`) verified zero occurrences

**Public contracts, events, Outbox, Inbox, workers, handlers, retries, timeouts, error contracts changed:**
- `AskAgentUseCase` accepts `tool_executor_factory` optional param (backward-compatible with existing `tool_executor`)
- `ask_agent_composer`, `ask_agent_stream_service`, `ask_job_worker` all create per-execution tool factory
- Agent worker registry reduced: outbox_dispatcher + ask_job_worker only (removed inbox_consumer, inbox_processor)

**Tests created or updated:**
- `test_event_self_subscriptions.py`: `test_agent_self_subscription_is_justified` → `test_agent_no_self_subscription`

**Validation commands:**
| Comando | Exit code |
|---|---|
| `python -m ruff check src/modules/agent/application/use_cases/ask_use_case.py src/modules/agent/application/composers/ask_agent_composer.py src/modules/agent/application/use_cases/ask_agent_stream_service.py src/modules/agent/infra/workers/ask_job_worker.py src/modules/agent/infra/workers/registry.py tests/architecture/test_event_self_subscriptions.py` | 0 |
| `python -m pytest tests/unit/agent/test_tools_application.py -q` | 0 (21 passed) |
| `python -m pytest tests/unit/agent/test_spec010_tool_executor_and_handlers.py -q` | 0 (8 passed) |
| `python -m pytest tests/integration/agent/test_tools_transaction.py -q` | 1 (5 pre-existing async failures, zero new failures) |
| `python -m pytest tests/architecture/test_event_self_subscriptions.py -v` | 0 (2 passed) |
| `python -m pytest tests/architecture/test_characterization_subscriptions.py tests/architecture/test_event_self_subscriptions.py -v` | 0 (5 passed) |

**Decisões:**
- Per-execution tool factory with `AgentUnitOfWork` opener chosen over stale `AgentToolExecutor(tool_repo)` to avoid closed-session access.
- `AgentToolExecutor` class kept for other consumers (e.g., direct tool API endpoints via `execute_tool_composer`).
- Agent inbox consumer/processor files kept on disk (not deleted) to minimize diff; only registry registrations removed. The files are now dead code.
- `tool_executor_factory` accepts `Callable[[UUID, dict], Awaitable[dict]]` for maximum flexibility — any async callable with `(tool_id, input_data) -> dict` works.

**Riscos:**
- Tool execution in ask/stream/job now opens an additional DB session per tool call (was previously shared). Acceptable — tool calls are relatively rare.
- Pre-existing async test failures (pytest-asyncio) unchanged.
- Agent inbox consumer/processor files remain on disk but unregistered.

### 007 — Padronizar produtores Outbox de todos os módulos

**Status:** completed
**Tipo:** messaging/modules
**Data:** 2026-06-16
**Scope:** module-communication-hardening

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` (verify branch) | 0 |
| `git status --short` | 0 |
| `Select-String "MeteringUsageRecorder\|ObservabilityTraceRecorder\|_legacy_mode\|agent\.#\|outbox\.write\(\|_do_save_assistant_message" src tests` | 0 (legacy patterns only in characterization tests) |

**Files changed:**
- `src/shared/messaging/outbox_writer.py` — added `routing_key` and `idempotency_key` required params to `OutboxEventWriter.write()` ABC
- `src/modules/billing/infra/database/repositories.py` — `SQLAlchemyOutboxEventWriter.write()` now accepts `routing_key`+`idempotency_key`, passes `event_version` to model
- `src/modules/core/infra/database/repositories.py` — same change
- `src/modules/identity/infra/database/repositories.py` — same change
- `src/modules/metering/infra/database/repositories.py` — same change
- `src/modules/observability/infra/database/repositories.py` — same change
- `src/modules/billing/application/use_cases/billing_use_cases.py` — 4 calls updated with `routing_key`+`idempotency_key`
- `src/modules/core/application/use_cases/create_project_use_case.py` — 1 call updated
- `src/modules/core/application/use_cases/create_api_key_use_case.py` — 1 call updated
- `src/modules/core/application/use_cases/update_project_use_case.py` — 1 call updated
- `src/modules/identity/application/use_cases/identity_use_cases.py` — 8 calls updated
- `src/modules/metering/application/use_cases/metering_use_cases.py` — 1 call updated
- `src/modules/observability/application/use_cases/observability_use_cases.py` — 2 calls updated

**Communication paths hardened:**
- All 18 standard-module `outbox.write()` call sites now pass `routing_key` (= event_type) and `idempotency_key` (= `{module}:{event_type}:{aggregate_id}`)
- `event_version` parameter no longer silently dropped — now passed to `OutboxEventModel`

**Public contracts, events, Outbox, Inbox, workers, handlers, retries, timeouts, error contracts changed:**
- `OutboxEventWriter.write()` ABC signature: added `routing_key: str` and `idempotency_key: str` as required params
- All 5 standard module writers updated to match new signature

**Tests created or updated:**
- Nenhum — existing architecture test `test_characterization_unversioned_events.py` already guards against unversioned events

**Validation commands:**
| Comando | Exit code |
|---|---|
| `python -m ruff check src/shared/messaging/outbox_writer.py src/modules/billing/... src/modules/core/... src/modules/identity/... src/modules/metering/... src/modules/observability/...` | 0 |
| `python -m pytest tests/architecture/test_event_versioning.py -q` | 0 (2 passed) |
| `python -m pytest tests/contract/events -q` | 0 (19 passed) |
| `python -m pytest tests/integration/billing tests/integration/core tests/integration/identity -q` | 0 (7 passed) |
| `python -m pytest tests/architecture/test_characterization_unversioned_events.py -v` | 0 (2 passed) |

**Decisões:**
- `routing_key` defaults to matching `event_type` in all call sites (canonical pattern).
- `idempotency_key` pattern: `{module}:{event_type}:{aggregate_id}` ensures uniqueness across modules.
- Agent module writers NOT affected (use different signature `write(event: AgentDomainEvent)`).
- `event_version` now correctly passed to model (was silently defaulting to 1).

**Riscos:**
- Pre-existing async test failures unchanged.
- Agent module's `SQLAlchemyAgentOutboxEventWriter` does not extend `OutboxEventWriter` (type mismatch exists pre-spec 007, out of scope).

## Próxima spec

`008-harden-rabbitmq-delivery-and-replay.md`
