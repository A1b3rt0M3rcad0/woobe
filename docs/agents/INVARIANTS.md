# Cross-cutting invariants

These are stable repository-wide rules that are easy to violate when changing one subsystem in isolation. Detailed behavior remains owned by domain code, tests, ADRs and topical documentation.

## Product and ownership

- Workspace is the account/ownership boundary; Project is the primary technical isolation boundary.
- A Project may own multiple Agent Networks.
- Network nodes have distinct node identities. Different nodes may select different frozen snapshots of the same Project-owned Agent; Agent identity does not identify a node.
- Agents and Agent Networks are distinct first-class runtime targets.

## Versioning and environments

- Draft is mutable.
- Staging is a validation environment.
- Production execution resolves immutable Agent or Network Releases.
- Platform versions are independent from Agent, Network, Skill and other domain-object versions.

## Execution

- A Run is a finite execution occurrence.
- A Session provides longitudinal execution identity/context.
- Agent Runs and Network Runs remain distinct even when they participate in the same causal execution tree.
- HTTP, streaming and asynchronous delivery are transport forms, not separate execution ontologies.
- Session-scoped External Context is fixed at Session scope; Run-scoped External Context is resolved per Run.

## Runtime persistence

- PostgreSQL owns durable application state and durable Run identity/state.
- Redis is runtime hot state, coordination and recovery/buffering infrastructure.
- MongoDB stores the incremental Run event journal.
- RabbitMQ supports asynchronous work delivery.

## Architecture

- `woobe-core` must not depend on `woobe-api`, `woobe-workers` or Enterprise implementation.
- `woobe-api` and `woobe-workers` consume Core through explicit module boundaries.
- Application layers do not import concrete infrastructure or HTTP frameworks.
- Composition assembles concrete implementations.
- `tooling/` is not part of the production dependency graph.
- Frontend checks are not security or authorization boundaries.

## Licensing

- Core and Enterprise are separate licensing boundaries.
- Core must remain runnable without activating Enterprise implementation.
- Moving or importing code does not silently change its licensing classification.

When a change intentionally alters one of these invariants, update the canonical architecture/licensing documentation and the relevant ADR or contract in the same pull request.
