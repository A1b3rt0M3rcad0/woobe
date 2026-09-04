# Woobe Quality Gate

`tooling/quality-gate` contains the repository architecture checker and declarative policies. It is engineering tooling and is not part of the production runtime dependency graph.

The installable Python package uses src layout at `tooling/quality-gate/src/quality_gate`. Governed bounded contexts own TOML policy data under `tooling/quality-gate/src/quality_gate/architecture/policies/`; the checker stays generic so new modules add policy data rather than module-specific branches.

The governed modules are `agent`, `chat_surface`, `core`, `identity`, `metering`, `network` and `observability`. Their policies act as a ratchet for architectural regressions while the checker remains module-agnostic.

## Canonical dependency direction

Every governed module follows this dependency graph:

```text
entrypoint -> composition -> presentation contracts
                     |----> application -> domain
                     |----> infra -------> domain
```

`composition` is the only module layer allowed to wire concrete implementations. `presentation`, `application`, `infra` and `domain` must never import `composition`. Application cannot depend on infrastructure or transport frameworks. Cross-bounded-context imports are forbidden by default.

`woobe-api` owns FastAPI, Starlette, routers, middleware and HTTP status/header mapping. It imports bounded contexts only through `entrypoint.py`. HTTP routers cannot create database sessions, instantiate repositories or import ORM models. `woobe-core` cannot depend on `woobe-api` or HTTP frameworks.

## Transactional composer contract

Every public function under `composition/composers/**` whose name ends in `_composer` is a short transactional composition root and must:

- be synchronous and contain wiring only;
- create exactly one configured `AgentUnitOfWork`;
- construct repositories explicitly with that same Unit of Work;
- never use Unit of Work repository/service-locator properties;
- return `TransactionalHandler` for request/response flows;
- return `StreamingTransactionalHandler` only when the database transaction is intentionally part of the stream lifecycle;
- pass the same Unit of Work instance to the wrapper;
- contain no control flow, nested runtime helpers, async work or operational configuration loading;
- expose no SQLAlchemy/FastAPI/Starlette/LangChain framework types in its imports or signature.

The architecture policy also protects long-lived runtime transaction ownership, repository/UoW boundaries, composition purity, transport ownership, and module API boundaries.

## Running the gate

From the repository root:

```bash
uv run pytest -q tests/quality_gate
PYTHONPATH=tooling/quality-gate/src \
  uv run python -m quality_gate.architecture.checker \
  --policy-dir tooling/quality-gate/src/quality_gate/architecture/policies
```

The GitHub Actions `Quality Gate` workflow uses the same tooling location. Policy violations are fixed in source or changed explicitly as an architecture decision; they are not suppressed merely to make CI green.
