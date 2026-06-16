---
name: projectrai-architecture-boundaries
description: Enforce ProjectRAI modular-monolith boundaries, import rules, shared-layer restrictions, worker placement, Unit of Work scope, and database ownership.
license: MIT
compatibility: opencode
metadata:
  project: ProjectRAI
  phase: architecture
  scope: boundaries
---

# ProjectRAI Architecture Boundaries

Use this skill when adding or reviewing code that may affect module boundaries, architecture tests, imports, `shared`, workers, database ownership, or Foreign Keys in ProjectRAI.

The target architecture is a modular monolith. `agent` becomes the bounded context for the former `ai`, `knowledge`, and `runtime` capabilities. Other modules stay separate and communicate through events for cross-module state changes.

## Absolute rules

- Do not create microservices.
- Do not keep `ai`, `knowledge`, and `runtime` as final independent modules.
- Do not import internals of another module.
- Do not create a Unit of Work that spans modules.
- Do not put business rules in workers.
- Do not put module domain objects, entities, value objects, DTOs, use cases, or handlers in `shared`.
- Do not create direct synchronous calls between modules for state changes.
- Do not create physical Foreign Keys across module schemas.
- Do not place concrete module workers in `src/workers`.
- Do not remove legacy modules before inventory, architecture tests, shims, and deprecation/removal specs.

## Layer rules

Allowed internal dependency direction inside a module:

- `presentation` may depend on `application` DTOs/use cases and public contracts.
- `application` may depend on `domain` and repository interfaces.
- `infra` may implement domain/application interfaces and integrate database, messaging, LLM, and workers.
- `domain` must not depend on `infra`, `presentation`, FastAPI, SQLAlchemy sessions, RabbitMQ clients, external SDKs, or other modules' internals.

`shared` may contain framework-neutral infrastructure, primitives, abstractions, base worker contracts, generic messaging helpers, and cross-cutting utilities. It must not know `agent`, `billing`, `metering`, `identity`, `tools`, `observability`, `ai`, `knowledge`, or `runtime` domain semantics.

## Import rules

Forbidden examples:

```python
from modules.billing.infra.repositories import BillingRepository
from modules.metering.domain.entities import UsageRecord
from modules.ai.infra.models import AgentModel
from modules.knowledge.application.use_cases import SearchKnowledgeBase
from modules.runtime.service.ask_use_case import AskUseCase
```

Preferred patterns:

- Same-module imports for internal use.
- Public contract modules when intentionally exposed.
- Event contracts and event envelopes for cross-module state propagation.
- Opaque external ids for references to other modules.
- Local projections/read models fed by Inbox events.

## Database ownership rules

A module owns its own tables and migrations. It may persist an external module id as a scalar value, but not as a physical constraint.

Allowed:

- `agent.* -> agent.*` Foreign Keys.
- `billing.* -> billing.*` Foreign Keys.
- `metering.* -> metering.*` Foreign Keys.
- `identity.* -> identity.*` Foreign Keys.
- `agent.external_customer_id UUID` as an opaque value with no FK.

Forbidden:

- `agent.* -> billing.*`
- `agent.* -> metering.*`
- `agent.* -> identity.*`
- `billing|metering|identity|core|tools|observability.* -> agent.*`
- Any final FK pointing to `ai`, `knowledge`, or `runtime` schemas.

Search for violations with:

```bash
rg "ForeignKey\(.*(ai|knowledge|runtime|billing|metering|identity|core|tools|observability)\." src/modules migrations tests || true
rg "op\.create_foreign_key|FOREIGN KEY" migrations src/modules || true
rg "modules\.(ai|knowledge|runtime)" src tests || true
```

## Worker rules

`src/shared/workers` may hold generic base classes, claim loops, registry contracts, runner infrastructure, and adapter-neutral behavior.

Concrete workers belong in:

```text
src/modules/<module>/infra/workers/
```

Root `src/workers` must not contain handlers, routing keys, queue names, event type branches, repositories, or business logic. A central runner may discover module registries and execute registered workers, but it must not know business events.

## Architecture test expectations

When implementing architecture tests, use static checks with low false negatives:

- Parse Python AST for imports rather than using text-only grep when possible.
- Check `shared` for forbidden domain naming patterns and imports.
- Check concrete worker placement and root worker leakage.
- Check `agent` does not import internals from non-agent modules.
- Check database boundary rules in models and migrations.
- Make temporary allowlists explicit, file-based, and tied to a removal spec.

Temporary allowlists must shrink over time. Final validation must fail if any active allowlist remains for `ai`, `knowledge`, or `runtime`.

## Review checklist

Before approving a patch, answer objectively:

1. Does every changed file belong to the active spec scope?
2. Did any module import another module's internals?
3. Did `shared` gain domain-specific behavior?
4. Did any worker gain business logic outside its owning module?
5. Did any Unit of Work coordinate more than one module?
6. Did any migration introduce cross-module FK or destructive rename without expand-migrate-contract?
7. Are tests enforcing the boundary instead of relying only on convention?
8. Was `/specs/execution/runtime.md` updated when required?
