# Changelog

Woobe follows Semantic Versioning for public releases. This file records user-visible platform changes.

## Unreleased

## [0.1.0] - 2026-09-24

### Added

- First public release of Woobe Core as a source-available control plane and runtime for production AI Agents and Agent Networks.
- Versioned Agent and Agent Network lifecycles with Draft, Staging, immutable Releases and Production activation.
- Stateful and stateless runtime execution paths with Sessions, Runs, Traces and streaming execution.
- Programmable Agent Network execution and production runtime coordination.
- Integrated runtime observability and persisted execution evidence.
- Knowledge/RAG Collections, Documents and versioned Vector Snapshots.
- External Agent capabilities through HTTP and MCP Tools.
- ChatSurface as an independently deployable browser-facing runtime surface.
- Self-hosted Core deployment through the root `compose.yaml`.

### Changed

- Product identity standardized on Woobe.
- `master` established as the integration branch.
- Repository organized into product `packages/`, engineering `tooling/` and cross-system `tests/` boundaries.
- Product licensing standardized on Woobe Core plus separately licensed Enterprise material.
- Core self-host distribution and release images aligned with explicit Core edition metadata.
- Core instance bootstrap and registration policy documented for self-hosting.
- Run persistence uses PostgreSQL for the durable Run registry, Redis for hot execution state/buffering and MongoDB for the incremental Run journal.

### Security

- Self-host configuration generation uses independent random secrets for authentication, persisted-secret encryption and ChatSurface session-token signing.
- Container artifacts run as non-root users and expose explicit Core license metadata.
- HTTP Tool and ChatSurface network policies default to restrictive behavior, with explicit opt-ins for local-network/insecure-origin use cases where supported.
