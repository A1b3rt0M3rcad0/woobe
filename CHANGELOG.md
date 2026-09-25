# Changelog

Woobe follows Semantic Versioning for public releases.

## Unreleased

## [0.13.0] - 2026-09-24

### Changed

- Core Web container configuration now resolves the public API and ChatSurface endpoints at container startup instead of baking deployment-specific URLs into the image.
- The same published `woobe-web:0.13.0` image can be reused across localhost, custom domains and production deployments through `WOOBE_PUBLIC_API_URL` and `WOOBE_PUBLIC_CHAT_EMBED_URL`.
- The Core image release workflow now publishes a deployment-neutral Web image and requires only the semantic version input.

### Fixed

- GHCR package paths normalize the repository owner to lowercase before publishing container images.
- Release-image checkout is pinned to the immutable `v<VERSION>` tag even when the workflow definition is dispatched from a newer `master`.

## [0.12.0] - 2026-09-24

First public release of Woobe. This is a pre-1.0 release: platform APIs and deployment contracts may still evolve between minor versions.

### Added

- Source-available, self-hostable Woobe Core control plane and runtime.
- Versioned Agents and Agent Networks with Draft, Staging, immutable Releases and Production activation.
- Sessions, Agent Runs, Network Runs and execution Traces as first-class runtime objects.
- Knowledge/RAG with Collections, Documents and immutable Vector Snapshots.
- Agent capabilities through HTTP and MCP Tools.
- Independently deployable ChatSurface for released Agents and Agent Networks.
- Core self-host topology and versioned Core container release workflow.

### Changed

- Product identity standardized on Woobe.
- `master` established as the integration branch.
- Repository reorganized into product `packages/`, engineering `tooling/` and cross-system `tests/` boundaries.
- Product licensing model standardized on Woobe Core plus separately licensed Enterprise.
- Core self-host distribution and release images aligned with explicit Core edition metadata.
- ChatSurface separated into its own product package and container artifact.
- Core instance bootstrap and registration policy documented for self-hosting.

### Security

- Self-host configuration generation uses independent random secrets for authentication, persisted-secret encryption and ChatSurface session-token signing.
- Container artifacts run as non-root users and expose explicit Core license metadata.

### Release provenance

The initial public-release comparison baseline is commit `50fdf358f7f4b8bd4ad5a6a59a68537087b599f0`. Release-note and contributor accounting for v0.12.0 starts after that commit.
