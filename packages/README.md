# Product packages

`packages/` contains Woobe product and distributable artifacts. Code placed here can participate in the supported Community build or define an explicit product boundary. Development-only helpers, repository quality tooling and cross-system test suites do not belong here.

## Contents

| Package | Responsibility |
| --- | --- |
| `woobe-core` | Community bounded contexts, domain/application code, shared technical infrastructure, runtime contracts, module-local presentation/composition, Alembic configuration and migration history. |
| `woobe-api` | HTTP process composition root: FastAPI bootstrap, middleware, transport registration and public API process entrypoints. |
| `woobe-workers` | Worker process composition root. Concrete worker implementations remain with the bounded context that owns them in Core. |
| `woobe-frontend` | Administrative control-plane frontend. It consumes HTTP/browser contracts and does not import Python Core. |
| `woobe-embed` | Independently built and deployable ChatSurface browser artifact. |
| `woobe-ee` | Reserved public boundary for separately licensed Enterprise capabilities. Community must not depend on proprietary implementation. |

## Dependency rules

API and Workers may depend on Core. Core must not depend on API, Workers or Enterprise implementation. Frontend and Embed communicate through external contracts rather than importing backend internals. Product packages must never depend on `tooling/`.

Migrations remain owned by `packages/woobe-core`; there is no `woobe-db` package in the current repository architecture. New top-level product packages should represent a real deployable or ownership boundary, not a convenience namespace.
