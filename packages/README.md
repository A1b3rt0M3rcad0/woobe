# Product packages

`packages/` contains Woobe product and distributable artifacts. Development-only helpers, repository quality tooling and cross-system test suites do not belong here.

## Contents and license boundary

| Package | Responsibility | License boundary |
| --- | --- | --- |
| `woobe-core` | Core bounded contexts, domain/application code, shared infrastructure, runtime contracts, module-local presentation/composition and migrations | **Woobe Core Sustainable Use License 1.0** |
| `woobe-api` | HTTP process composition root | **Woobe Core Sustainable Use License 1.0** |
| `woobe-workers` | Worker process composition root | **Woobe Core Sustainable Use License 1.0** |
| `woobe-runtime-client` | Shared browser Runtime protocol/observer primitives consumed by Frontend and Embed | **Woobe Core Sustainable Use License 1.0** |
| `woobe-frontend` | Administrative control-plane frontend | **Woobe Core Sustainable Use License 1.0** |
| `woobe-embed` | Independently built and deployable ChatSurface browser artifact | **Woobe Core Sustainable Use License 1.0** |
| `woobe-ee` | Enterprise product boundary | **Separate Enterprise license / agreement** |

The controlling Core license is repository-root `LICENSE.md`. The Enterprise boundary is described in `LICENSE_EE.md`.

## Dependency rules

API and Workers may depend on Core. Core must not depend on API, Workers or Enterprise implementation. Frontend and Embed may consume `woobe-runtime-client` for browser-side Runtime protocol semantics; the Runtime client must not import backend internals. Product packages must never depend on `tooling/`.

Migrations remain owned by `packages/woobe-core`; there is no separate database package in the current repository architecture.
