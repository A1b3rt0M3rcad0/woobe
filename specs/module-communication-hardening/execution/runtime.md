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
| 001 | pending |
| 002 | pending |
| 003 | pending |
| 004 | pending |
| 005 | pending |
| 006 | pending |
| 007 | pending |
| 008 | pending |
| 009 | pending |

## Specs executadas

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
| ID | Defect | Corrective spec |
|---|---|---|
| D001 | Missing `await` on `outbox.write()` (ask_use_case.py ×5, ask_agent_stream_service.py ×4) | 001 |
| D002 | MeteringUsageRecorder/ObservabilityTraceRecorder adapters still used by ask_job_worker.py | 002 |
| D003 | `_legacy_mode` flag still active | 001 |
| D004 | `_do_save_assistant_message` legacy direct-write | 001 |
| D005 | Unversioned events in billing/core/identity | 003 |
| D006 | `agent.#` self-subscription routing key | 003 |
| D007 | Metering/observability consumers missing 4 event types | 004, 005 |

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
- 7 known defects remain active; zero have been fixed in this spec.
- Characterization tests depend on KNOWN_VIOLATIONS sets remaining accurate as code changes.

## Próxima spec

`001-fix-agent-async-and-transaction-boundaries.md`
