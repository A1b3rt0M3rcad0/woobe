# Testing and validation

Context Manager coverage is split between algorithm tests, shared Runtime tests, recovery tests and architecture gates.

## Manager algorithm tests

Test decisions that distinguish the Manager:

~~~text
capacity-aware caps
inventory-based decisions
phase-aware behavior
source priorities
summary trigger
summary refresh threshold
summary failure mode
state mutation
checkpoint boundary
Skills materialization decision
~~~

Standard should explicitly prove it does not call semantic summary even if Summary Policy is enabled.

Adaptive coverage lives in `tests/unit/agent/test_adaptive_context_manager.py` and proves:

- semantic summary under pressure;
- durable Context checkpoint;
- summary transformation evidence;
- reuse without a second model call;
- fallback to deterministic selection on summary failure.

## SDK/runtime isolation

`test_context_manager_programming.py` proves configured/effective policy isolation, validation, capacity, inventory, invocation metadata and primitive invariants.

## Recovery

`test_run_recovery_worker.py` covers Context state recovery:

- a Context checkpoint newer than the safe Execution checkpoint is merged into recovery state;
- a newer Context state already embedded in the Execution checkpoint wins over an older Context event;
- a side-effect-free Run with only Context state may restart from the beginning while reusing that state;
- Tool causality is still evaluated only against true Execution checkpoints.

## Shared materialization

Generic tests continue to cover mandatory context, model-capacity clamp, source caps, truncation, External Context, Skills, Snapshot accounting, contribution provenance, pressure and budget metrics.

Do not replicate the full deterministic assembler test suite for each Manager.

## Resolver/catalog parity

Every selectable built-in Manager must exist in both `resolver.py` and `context_manager_registry.py`.

Current built-ins:

~~~text
standard
adaptive
~~~

## Legacy compatibility

Historical `stdcm:v1`, `stdcm:v2`, `default:v1`, `stdcm` and `default` selections must still read as `standard`.

## Architecture gates

Relevant gates include `tests/architecture/test_context_assembler_boundary.py` and Agent policy rules `ARCH082`–`ARCH084`.

## Definition of Done

- [ ] Manager is one flat algorithm file unless a platform-level reason requires otherwise;
- [ ] `name` is stable/lowercase/unversioned;
- [ ] `state_type` is declared;
- [ ] `assemble` is async;
- [ ] no provider/message/database/journal dependency leaks into the Manager;
- [ ] side effects happen only through Runtime primitives;
- [ ] policy is read as configured input and effective mutation uses primitives;
- [ ] mandatory source invariants remain intact;
- [ ] state is serializable and recovery-safe;
- [ ] summary/checkpoint behavior has algorithm tests when used;
- [ ] resolver/catalog names match;
- [ ] architecture gates pass;
- [ ] relevant backend/frontend/acceptance workflows pass.

## Focused backend suite

~~~bash
uv run pytest -q \
  tests/unit/agent/test_context_manager_programming.py \
  tests/unit/agent/test_adaptive_context_manager.py \
  tests/unit/agent/test_context_assembler_boundary.py \
  tests/unit/agent/test_context_engineering_core.py \
  tests/unit/agent/test_run_recovery_worker.py \
  tests/architecture/test_context_assembler_boundary.py
~~~

Do not claim a test or workflow passed until it actually completed.
