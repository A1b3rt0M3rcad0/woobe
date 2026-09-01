# ADR 0004 — Package workspace and process boundaries

Status: accepted for MVP.

Woobe Community is organized as a repository-level `packages/` workspace. `woobe-core` owns the Community bounded contexts, their domain and application code, shared technical infrastructure, runtime contracts, bounded-context presentation/composition code, and the current Alembic migration surface. `woobe-core` is therefore a product Core package, not a framework-neutral library.

`woobe-api` owns the HTTP process composition root: FastAPI application bootstrap, process-level middleware, transport registration, and public HTTP entrypoints. Module-local routers, controllers, schemas, and composers remain colocated with their bounded context in `woobe-core` so a repository packaging refactor does not split each business module across process packages.

`woobe-workers` owns only the worker process composition root. Concrete worker implementations remain with the bounded context that owns their behavior under `woobe-core/src/modules/<module>/infra/workers/`. The worker process discovers and composes those implementations; Core must not import the Workers package.

Alembic configuration and migration history remain in `woobe-core`, at `woobe-core/alembic.ini` and `woobe-core/migrations/`. A standalone database/migration package is not part of this repository cutover; if introduced, it must be handled by a dedicated ADR/PR so its runtime, deployment, packaging, and ownership consequences are evaluated independently. `woobe-frontend` owns the control-plane frontend and ChatSurface embed build. `woobe-testkit`, `woobe-mock`, and `woobe-e2e` are test boundaries. `woobe-ee` is a reserved public boundary only; it contains no proprietary runtime implementation in the Community distribution.

The dependency direction is intentionally one-way: API and Workers may depend on Core; Core must not depend on API, Workers, or Enterprise implementation. Frontend and Embed consume HTTP contracts rather than importing Python Core.

Internal Python packages are installed as editable distributions in runtime and backend-test images. This removes runtime `PYTHONPATH` coupling while preserving stable repository-relative source paths required by existing migration and preflight contracts. The root dependency manifest and lock remain authoritative for the MVP; adopting a formal uv workspace lock is a separate change and is not required for this repository cutover.

This decision favors a small, operational package boundary over moving every FastAPI-facing bounded-context file out of Core. A stricter framework-neutral Core can be reconsidered only when there is a concrete need for independently reusable domain packages or multiple transport implementations that justify the additional split.
