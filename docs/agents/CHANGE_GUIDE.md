# Change guide for coding agents

Use this guide after locating the owning concept in `DOMAIN_INDEX.md`.

## Before editing

1. Read the existing implementation and nearby tests.
2. Identify the owning bounded context and layer.
3. Read the relevant ADR/topical documentation.
4. Check whether the behavior is a public contract, persisted contract or release invariant.
5. Prefer extending an existing abstraction over creating a parallel path.

## Route the change

### Domain or business rule

Change the owning bounded context. Keep domain rules out of HTTP handlers and frontend-only validation. Update domain/application tests and any public contract documentation affected.

### HTTP/API behavior

Start from the owning Core entrypoint/presentation contract, then update `woobe-api` transport composition. Do not move persistence or business rules into the API host.

### Background execution

Use the owning module's `background_boundary.py` or explicit entrypoint and compose it from `woobe-workers`. Do not let Workers reach into arbitrary Core internals.

### Runtime execution

Read `docs/ARCHITECTURE.md`, `docs/runtime/STREAMING.md` and `docs/runtime/UNIFIED_OBSERVER.md` as applicable. Preserve Run/Session identity, exact release resolution, event ordering and observable terminal behavior.

### Agent or Network lifecycle

Validate Draft/Staging/Production behavior, immutable release resolution, session behavior and runtime keys for the affected target. Changes shared by Agent and Network should not create divergent public semantics without an explicit reason.

### Knowledge/RAG

Preserve immutable Vector Snapshot identity and versioned runtime bindings. Read the Agent RAG documentation before changing retrieval or context-assembly behavior.

### Tools/MCP

Preserve agent-scoped permissions, execution contracts and network-security policy. Read `docs/runtime/MCP_TOOLS.md`.

### Frontend

Treat backend/API contracts as authoritative. Reuse shared operational/runtime primitives where they already exist. Do not implement ownership, authorization or release immutability only in the browser.

### Repository/package boundaries

Read ADR 0004 and `docs/ARCHITECTURE.md`. Do not introduce reverse dependencies from Core into process hosts, tooling or Enterprise implementation.

### Licensing or distribution

Read `LICENSE.md`, `LICENSE_EE.md`, `LICENSING.md`, `TRADEMARKS.md` and `THIRD_PARTY_NOTICES.md` before changing package/distribution boundaries.

### Release work

Follow `RELEASING.md` exactly. Release preparation uses the canonical Conventional Commit subject documented there.

## Validation

Use the narrowest relevant tests while iterating, then run the repository-required validation for the changed surface.

Canonical backend validation:

```bash
docker compose -f compose.test.yaml up --build --exit-code-from tests tests
```

See `docs/testing/COMPOSE_TESTS.md` for backend topology. Frontend, container, acceptance, security and release validation are separate surfaces and must be run when applicable.

## Documentation rule

Do not place temporary implementation plans in durable docs. Update durable documentation when public contracts, architecture, operations, licensing or repository policy change.

Commit and pull-request messages follow `CONTRIBUTING.md`.
