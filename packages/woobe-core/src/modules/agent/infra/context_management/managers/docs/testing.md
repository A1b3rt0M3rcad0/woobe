# Testing and validation

A Context Manager must prove two things:

1. its algorithm programs the intended effective context;
2. it integrates through generic Context Manager Runtime without Manager-specific infrastructure.

## Algorithm tests

Add focused unit tests under `tests/unit/agent/` for the decisions that make the Manager different.

Typical assertions cover Session window, source inclusion/exclusion, caps, priorities, ordering, deduplication, budget and optional runtime sources.

## SDK isolation tests

Configured policy and effective policy are intentionally separate.

Tests should prove:

- SDK primitives change the effective outcome;
- the original request policy is not mutated;
- direct mutation of `ctx.policy` does not bypass primitives;
- mandatory priority invariants cannot be downgraded.

The canonical coverage lives in `tests/unit/agent/test_context_manager_programming.py`.

## Runtime tests

Generic Runtime coverage should verify:

~~~text
mandatory SYSTEM/current input preservation
model-capacity clamp
output reserve handling
source caps
safe text truncation
safe External Context compaction
Context Snapshot accounting
ContextContribution provenance
transformation evidence
measurement status
pressure status
Skills materialization
~~~

Do not duplicate all generic Runtime tests per Manager.

## Catalog and resolver parity

Every built-in selectable Manager must exist in both `resolver.py` and `context_manager_registry.py`, with identical stable names.

## Legacy compatibility

Standard must continue to read historical identities `stdcm:v1`, `stdcm:v2`, `default:v1`, `stdcm` and `default` as `standard`.

## Architecture gates

Relevant checks include:

~~~text
tests/architecture/test_context_assembler_boundary.py
ARCH082  resolver composition boundary
ARCH083  concrete Manager dependency boundary
ARCH084  Context Manager Runtime boundary
~~~

## Definition of Done

- [ ] one concrete Manager file was added under `infra/context_management/managers/`;
- [ ] no Manager-specific Runtime package was introduced;
- [ ] `name` is stable, lowercase and unversioned;
- [ ] `ctx.policy` is treated only as configured input;
- [ ] effective behavior is expressed through SDK primitives;
- [ ] SYSTEM/current USER_INPUT invariants remain intact;
- [ ] no provider/LangChain message construction exists in the Manager;
- [ ] no Snapshot/Contribution construction exists in the Manager;
- [ ] no provider/database/execution-runtime dependency exists in the Manager;
- [ ] runtime implementation is registered in resolver;
- [ ] product metadata is registered in catalog;
- [ ] resolver/catalog names are in parity;
- [ ] behavior tests cover Manager-specific decisions;
- [ ] architecture gates pass;
- [ ] relevant backend/frontend tests pass when contracts changed.

## Focused validation

~~~bash
uv run pytest -q tests/unit/agent/test_context_manager_programming.py tests/unit/agent/test_context_assembler_boundary.py tests/unit/agent/test_context_engineering_core.py tests/architecture/test_context_assembler_boundary.py
~~~

Do not claim test or CI success unless it actually completed.
