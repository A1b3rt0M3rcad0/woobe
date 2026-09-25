# Product packages

`packages/` contains Woobe product and distributable artifacts. Development-only helpers, repository quality tooling and cross-system test suites do not belong here.

## Primary release units

Woobe has exactly five primary product release units:

| Release unit | Source package | Distribution role |
| --- | --- | --- |
| Core | `woobe-core` | Python domain/runtime library and migrations; not a standalone container |
| API | `woobe-api` | Independently deployable HTTP/API container |
| Workers | `woobe-workers` | Independently deployable background-execution container |
| Web | `woobe-frontend` | Independently deployable administrative Web container |
| ChatSurface | `woobe-embed` | Independently deployable Embed/ChatSurface container |

`woobe-runtime-client` and `woobe-ui` are shared internal browser libraries consumed at build time by the primary Web artifacts. They are not independent deployment units. `woobe-ee` remains a separate Enterprise implementation/license boundary and is not a Core release unit.

The four deployable Core container artifacts are therefore `woobe-api`, `woobe-workers`, `woobe-web` and `woobe-chat-embed`. The `woobe-core` release unit is consumed by API and Workers as a Python package rather than exposed as an artificial process/container.

## Contents and license boundary

| Package | Responsibility | License boundary |
| --- | --- | --- |
| `woobe-core` | Core bounded contexts, domain/application code, shared infrastructure, runtime contracts, module-local presentation/composition and migrations | **Woobe Core Sustainable Use License 1.0** |
| `woobe-api` | HTTP process composition root | **Woobe Core Sustainable Use License 1.0** |
| `woobe-workers` | Worker process composition root | **Woobe Core Sustainable Use License 1.0** |
| `woobe-runtime-client` | Shared browser Runtime protocol/observer primitives consumed by Frontend and Embed | **Woobe Core Sustainable Use License 1.0** |
| `woobe-ui` | Shared UI components and design tokens | **Woobe Core Sustainable Use License 1.0** |
| `woobe-frontend` | Administrative control-plane frontend | **Woobe Core Sustainable Use License 1.0** |
| `woobe-embed` | Independently built and deployable ChatSurface browser artifact | **Woobe Core Sustainable Use License 1.0** |
| `woobe-ee` | Enterprise implementation boundary | **Woobe Enterprise License 1.0; production requires express written authorization** |

The controlling texts are repository-root [LICENSE.md](../LICENSE.md), [LICENSE_EE.md](../LICENSE_EE.md) and [TRADEMARKS.md](../TRADEMARKS.md). Third-party components retain their own terms.

The Enterprise Covered Paths are `packages/woobe-ee/**`; copied, modified and compiled Enterprise material retains its license outside those paths. Independent integration code does not become Enterprise merely because it imports or invokes EE. Non-production Enterprise activities are permitted as specified in its license; production requires valid express written authorization. Neither software license grants platform resale or commercial brand rights.

## Dependency rules

API and Workers may depend on Core. Core must not depend on API, Workers or Enterprise implementation. Frontend and Embed may consume `woobe-runtime-client` for browser-side Runtime protocol semantics; the Runtime client must not import backend internals. Product packages must never depend on `tooling/`.

Migrations remain owned by `packages/woobe-core`; there is no separate database package in the current repository architecture.
