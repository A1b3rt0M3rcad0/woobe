# Changelog

Woobe follows Semantic Versioning for public releases.

## Unreleased

## [0.14.2] - 2026-09-25

### Added

- Release-candidate automation now builds immutable multi-architecture API, Workers, Frontend and Embed images before a version tag is created, with provenance/SBOM attestations and smoke validation.
- Package-build CI now builds and clean-installs release-bearing Python artifacts and validates that all platform package versions remain synchronized.
- Acceptance validation now exercises schema upgrades from the previous published release while preserving a persisted-state probe.

### Changed

- Core image publication now promotes the exact previously validated candidate digests instead of rebuilding release images during publication.
- Acceptance and container validation now exercise the same prebuilt application-image topology used by release candidates, including explicit Workers heartbeat health checks.
- Published release images are smoke-tested again after promotion to the semantic-version tags.

### Fixed

- Release identity validation now rejects mismatched manifest versions, release commits and candidate images before publication.
- v0.14.2 supersedes the incomplete v0.14.1 tag; v0.14.1 Core image publication did not complete because that tag did not contain the required platform-version and canonical release-commit identity.


## [0.14.0] - 2026-09-24

### Added

- Workers are now a first-class container release artifact published as `woobe-workers:<VERSION>`.
- Container quality generates an independent Workers SBOM, vulnerability scan and runtime-isolation check.
- The Core Python package declares its runtime dependency metadata and is built independently during release validation.

### Changed

- Woobe now defines five primary product release units: Core, API, Workers, Web and ChatSurface.
- API and Workers use separate Docker targets and contain only their own process-host source plus the shared `woobe-core` package.
- The supported self-host Compose topology selects the API and Workers targets explicitly, allowing the two process classes to be scaled and rolled out independently.
- The release workflow publishes four independently deployable container artifacts: `woobe-api`, `woobe-workers`, `woobe-frontend` and `woobe-embed`.
- `woobe-runtime-client` and `woobe-ui` remain internal shared browser libraries rather than standalone deployment units. Frontend and Embed distribution names now match their canonical source package names.

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
