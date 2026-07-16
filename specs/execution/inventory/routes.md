# Current API route map

- `src/main.py` creates the FastAPI application and calls `include_router` for public module routes.
- Identity routes are defined in `src/modules/identity/presentation/routes.py` and `auth_endpoints.py`.
- Authentication includes registration, login, refresh, logout and `/identity/users/me`.
- Core routes are defined in `src/modules/core/presentation/routes.py`.
- Core exposes organization/project operations, API keys and project overview endpoints.
- Agent routes are defined in `src/modules/agent/presentation/routes.py`.
- Agent exposes agent configuration, releases, credentials, tools and knowledge operations.
- Runtime execution routes include synchronous ask, jobs and SSE streaming.
- Observability routes are defined in `src/modules/observability/presentation/routes.py`.
- Metering routes are defined in `src/modules/metering/presentation/routes.py`.
- Billing routes are defined in `src/modules/billing/presentation/routes.py`.
- Private routes are guarded by the shared authentication and tenancy dependency.
- Runtime API-key routes derive project ownership from the authenticated key principal.
- The historical `/ai`, `/knowledge` and `/runtime` bounded contexts are consolidated behind current module routes.
- `APIRouter` prefixes and controller adapters preserve module ownership.
- Route contracts are exercised with ASGI clients under `tests/modules/` and `tests/integration/`.
- Health is exposed by the application bootstrap for container smoke validation.
