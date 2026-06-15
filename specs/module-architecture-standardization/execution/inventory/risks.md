# Standardization Risk Register and Execution Order

**Date:** 2026-06-14
**Branch:** project-rai-playground_module-architecture-standardization
**SHA:** 1e87c8e

## Notes
- Generated during spec 019 execution.
- Synthesized from all 10 inventories (specs 010-018).

## Consolidated Risk Register

| # | Risk | Severity | Source Inventory | Mitigation | Target Spec |
|---|---|---|---|---|---|
| R01 | Agent has both AgentUnitOfWork and PostgresUnitOfWork in composers — redundant, bypasses module-specific UoW | high | transactions.md | Migrate all agent composers to AgentUnitOfWork | 025 |
| R02 | 6 modules (billing, core, identity, metering, observability, tools) have NO module-specific UoW | high | transactions.md | Create per-module UoW classes | 036-086 |
| R03 | 89 composers across all modules hardcode PostgresUnitOfWork (shared generic) | high | transactions.md | Inject module-specific UoW via DI composers | 025-036 |
| R04 | `ask_agent_stream_service.py` commits directly via `await db_session.commit()` — bypasses UoW entirely | high | transactions.md | Refactor to use AgentUnitOfWork | 026 |
| R05 | 33 cross-module Foreign Keys identified | critical | database-ownership.md | Expand-migrate-contract, replace with opaque UUIDs | 099 |
| R06 | 32 legacy schema references (ai, knowledge, runtime) in module models | critical | database-ownership.md | Migrate to agent schema | 099 |
| R07 | 3 schemas legados (ai, knowledge, runtime) pendentes de migração | high | database-ownership.md | Schema migration via expand-migrate-contract | 099 |
| R08 | Only agent uses versioned event naming (`agent.*.v1`); 6 modules use unversioned | high | events.md | Standardize envelopes across all modules | 090 |
| R09 | Agent has 3 separate OutboxEventWriter implementations (base, knowledge, runtime) | medium | events.md | Consolidate into single agent writer | 026 |
| R10 | Agent has 3 separate outbox/inbox model pairs | medium | events.md | Consolidate | 026 |
| R11 | Legacy event namespaces (ai/, knowledge/, runtime/) still in agent use_cases | high | events.md | Migrate to agent namespace | 029 |
| R12 | Only agent has `AgentRabbitMQPublisher` + `AgentInboxEventRouter`; 6 modules have none | high | events.md, workers.md | Create per-module publishers and routers | 037-087 |
| R13 | No dead-letter or retry-with-backoff policy found | medium | events.md | Standardize retry/dead-letter | 094 |
| R14 | Only agent has concrete workers (4); 5 modules have empty registry stubs | high | workers.md | Create per-module workers | 037-087 |
| R15 | core has no workers directory at all | high | workers.md | Create core workers | 047 |
| R16 | `AskJobWorker` imports from `modules.metering` and `modules.observability` — cross-module dependency | high | workers.md | Refactor to event-driven | 027 |
| R17 | 1 cross-module production import: agent → identity (providers.py imports identity service) | high | imports.md | Refactor to messaging/opaque IDs | 029 |
| R18 | Agent has 4 routers (3 legacy: /ai, /knowledge, /runtime) | high | routes.md | Consolidate into single /agent router | 028 |
| R19 | Rotas podem quebrar durante moves | high | routes.md | Shim temporários e testes de contrato | 028 |
| R20 | 34 pre-existing architecture test failures (old spec suite references) | medium | tests-bootstrap.md | Fix or remove old tests | 107 |
| R21 | e2e tests directory empty | low | tests-bootstrap.md | Create e2e tests | 105 |
| R22 | Async Alembic env uses mixed sync/async URL conversion (fragile) | medium | tests-bootstrap.md | Standardize expand-migrate-contract | 098 |
| R23 | Wildcard model imports in migrations/env.py | medium | tests-bootstrap.md | Replace with explicit imports | 098 |
| R24 | Ruff F821/F401/F841 erros pré-existentes (25 errors, not from migration) | low | all | Accept as pre-existing, fix in cleanup | 107 |
| R25 | `rg` and `find` unavailable on Windows | low | all | Substitute with PowerShell equivalents | N/A |

## Execution Order Recommendation

Based on inventory findings and existing MANIFEST.md:

### Phase 1: Agent Baseline (specs 020-029)
Stabilize agent before replicating pattern. Highest priority:
1. Audit agent as canonical reference (020)
2. Normalize agent domain (021), application (022), composers (023), database (024)
3. Make AgentUnitOfWork the transaction boundary (025) — fixes R01, R03
4. Normalize agent messaging (026) — fixes R09, R10
5. Normalize agent workers (027) — fixes R16
6. Normalize agent presentation (028) — fixes R18, R19
7. Lock agent with architecture tests (029) — fixes R17

### Phase 2-7: Per-Module Standardization (specs 030-089)
Order: identity (030-039) → core (040-049) → billing (050-059) → metering (060-069) → observability (070-079) → tools (080-089)
Each module: map → skeleton → domain → application → presentation → infra → UoW → messaging → tests → cleanup
Fixes R02, R03, R12, R14, R15

### Phase 8: Cross-cutting Standards (specs 090-099)
1. Versioned event envelope (090) — fixes R08
2. Outbox contract (091)
3. Inbox contract (092)
4. RabbitMQ topology (093)
5. Idempotency, retry, dead letter (094) — fixes R13
6. Central runner wiring (095)
7. Clean shared (096)
8. Bootstrap standardization (097) — fixes R23
9. Alembic expand-migrate-contract (098) — fixes R22
10. Remove cross-module FKs (099) — fixes R05, R06, R07

### Phase 9: Final Validation (specs 100-109)
Final tests, cleanup, validation, and report — fixes R20, R21, R24

## Blockers

| Blocker | Severity | Description | Required Before |
|---|---|---|---|
| Branch divergence | critical | If `last_validated_sha` differs from HEAD, re-run inventories | Spec 020 |
| Pre-existing test failures (34) | medium | Must not block discovery specs; must be resolved before spec 108 | Spec 108 |

## Acceptance Criteria

- [x] `risks.md` exists and is not empty
- [x] SHA of inventory registered: `1e87c8e`
- [x] All risks from prior inventories consolidated
- [x] Execution order specified per phase
- [x] Blockers documented
