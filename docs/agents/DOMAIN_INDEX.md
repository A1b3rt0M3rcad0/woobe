# Domain ownership index

This document routes coding agents to the current owner of a Woobe concept. It is an index, not a replacement for domain code or topical documentation.

| Concept | Primary code owner | Read next |
| --- | --- | --- |
| Workspace, membership, identity | `packages/woobe-core/src/modules/identity/` | `docs/ARCHITECTURE.md`, `docs/adr/0002-authentication-tenancy.md` |
| Project, Runtime Keys, project-level resources | `packages/woobe-core/src/modules/core/` | `docs/ARCHITECTURE.md` |
| Agent, Agent Release, Agent Session, Agent Run | `packages/woobe-core/src/modules/agent/` | `docs/ARCHITECTURE.md`, `docs/runtime/` |
| Agent Network, Network Release, Network Session, Network Run | `packages/woobe-core/src/modules/network/` | `docs/ARCHITECTURE.md`, `docs/runtime/` |
| External Context | Agent and Network application/domain boundaries | `docs/ARCHITECTURE.md` |
| Skills | `packages/woobe-core/src/modules/agent/domain/skills.py` and Agent application services | `docs/skills/` |
| Knowledge, Collections, Documents, Vector Snapshots, RAG | Agent bounded context | `packages/woobe-core/src/modules/agent/application/rag/README.md`, `docs/ARCHITECTURE.md` |
| Tools, HTTP Tools, MCP Tools | Agent bounded context | `docs/runtime/MCP_TOOLS.md` |
| Providers, credentials and provider models | Agent bounded context | `docs/CONTRIBUTING_PROVIDERS.md` |
| ChatSurface | `packages/woobe-core/src/modules/chat_surface/` plus `packages/woobe-embed/` | `docs/runtime/CHAT_SURFACE.md` |
| Usage and metering | `packages/woobe-core/src/modules/metering/` | `docs/ARCHITECTURE.md` |
| Observability and runtime evidence | `packages/woobe-core/src/modules/observability/` plus Agent/Network event projectors | `docs/runtime/UNIFIED_OBSERVER.md` |
| HTTP process composition | `packages/woobe-api/` | `docs/ARCHITECTURE.md`, ADR 0004 |
| Background execution host | `packages/woobe-workers/` | `docs/ARCHITECTURE.md`, ADR 0004 |
| Browser runtime protocol | `packages/woobe-runtime-client/` | `docs/runtime/STREAMING.md` |
| Control-plane frontend | `packages/woobe-frontend/` | relevant feature + API/runtime contract |
| Shared UI primitives | `packages/woobe-ui/` | consuming frontend code |
| Enterprise implementation | `packages/woobe-ee/` | `LICENSE_EE.md`, `LICENSING.md` |

## Bounded-context layout

Core bounded contexts generally follow:

```text
domain/
application/
infra/
presentation/
composition/
entrypoint.py
background_boundary.py
```

Use the owning module's public entrypoints/boundaries instead of importing across internal layers.

If ownership is unclear, inspect the existing entity, repository interface, use case and tests before creating a new abstraction or module.
