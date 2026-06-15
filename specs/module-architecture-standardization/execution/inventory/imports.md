# Import Dependency Map

**Date:** 2026-06-14
**Branch:** project-rai-playground_module-architecture-standardization
**SHA:** d6ee29c

## Notes
- Generated during spec 012 execution.
- `rg` unavailable; substituted with `Select-String -Pattern '^(from modules\.|import modules\.)'`.
- `scripts/architecture/import_graph.py` not found — cannot produce automated graph.

## Cross-Module Imports (src/modules/)

### agent imports from other modules

| Source File | Import | Dependency Type |
|---|---|---|
| `src/modules/agent/application/providers.py` | `from modules.identity.service.use_cases` | service (identity) |
| `src/modules/agent/infra/database/models.py` | `from modules.agent.domain...` | intra-module |
| `src/modules/agent/infra/database/repositories.py` | `from modules.agent.domain...` | intra-module |
| `src/modules/agent/infra/database/unit_of_work.py` | `from modules.agent.domain...` | intra-module |

**agent** has minimal cross-module imports beyond same-domain references. Providers import identity service for DI composition.

### billing imports

| Source File | Import | Dependency Type |
|---|---|---|
| `src/modules/billing/domain/entities.py` | `from modules.billing.domain...` | intra-module |
| `src/modules/billing/infra/...` | `from modules.billing.domain...`, `from modules.billing.infra...` | intra-module |
| `src/modules/billing/presentation/routes.py` | `from modules.billing.application.composers...` | intra-module |
| `src/modules/billing/service/use_cases.py` | `from modules.billing.domain...`, `from modules.billing.service...` | intra-module |
| `src/modules/billing/application/composers/*.py` | `from modules.billing.infra...`, `from modules.billing.service...`, `from modules.billing.presentation.controllers...` | intra-module |

### core imports

| Source File | Import | Dependency Type |
|---|---|---|
| `src/modules/core/domain/entities.py` | `from modules.core.domain...` | intra-module |
| `src/modules/core/infra/...` | `from modules.core.domain...`, `from modules.core.infra...` | intra-module |
| `src/modules/core/presentation/routes.py` | `from modules.core.application.composers...` | intra-module |
| `src/modules/core/service/use_cases.py` | `from modules.core.domain...`, `from modules.core.service...` | intra-module |
| `src/modules/core/application/composers/*.py` | `from modules.core.infra...`, `from modules.core.service...`, `from modules.core.presentation.controllers...` | intra-module |

### identity imports

| Source File | Import | Dependency Type |
|---|---|---|
| `src/modules/identity/domain/...` | `from modules.identity.domain...` | intra-module |
| `src/modules/identity/infra/...` | `from modules.identity.domain...`, `from modules.identity.infra...` | intra-module |
| `src/modules/identity/presentation/routes.py` | `from modules.identity.application.composers...` | intra-module |
| `src/modules/identity/service/use_cases.py` | `from modules.identity.domain...`, `from modules.identity.service...` | intra-module |
| `src/modules/identity/application/composers/*.py` | `from modules.identity.infra...`, `from modules.identity.service...`, `from modules.identity.presentation.controllers...` | intra-module |

### metering imports

| Source File | Import | Dependency Type |
|---|---|---|
| `src/modules/metering/domain/...` | `from modules.metering.domain...` | intra-module |
| `src/modules/metering/infra/...` | `from modules.metering.domain...`, `from modules.metering.infra...` | intra-module |
| `src/modules/metering/presentation/routes.py` | `from modules.metering.application.composers...` | intra-module |
| `src/modules/metering/service/use_cases.py` | `from modules.metering.domain...`, `from modules.metering.service...` | intra-module |
| `src/modules/metering/application/composers/*.py` | `from modules.metering.infra...`, `from modules.metering.service...`, `from modules.metering.presentation.controllers...` | intra-module |

### observability imports

| Source File | Import | Dependency Type |
|---|---|---|
| `src/modules/observability/domain/...` | `from modules.observability.domain...` | intra-module |
| `src/modules/observability/infra/...` | `from modules.observability.domain...`, `from modules.observability.infra...` | intra-module |
| `src/modules/observability/presentation/routes.py` | `from modules.observability.application.composers...` | intra-module |
| `src/modules/observability/service/use_cases.py` | `from modules.observability.domain...`, `from modules.observability.service...` | intra-module |
| `src/modules/observability/application/composers/*.py` | `from modules.observability.infra...`, `from modules.observability.service...`, `from modules.observability.presentation.controllers...` | intra-module |

### tools imports

| Source File | Import | Dependency Type |
|---|---|---|
| `src/modules/tools/domain/...` | `from modules.tools.domain...` | intra-module |
| `src/modules/tools/infra/...` | `from modules.tools.domain...`, `from modules.tools.infra...` | intra-module |
| `src/modules/tools/service/use_cases.py` | `from modules.tools.domain...`, `from modules.tools.service...`, `from modules.tools.infra...`, `from modules.tools.presentation...` | intra-module |
| `src/modules/tools/application/composers/*.py` | `from modules.tools.infra...`, `from modules.tools.service...`, `from modules.tools.presentation.controllers...` | intra-module |
| `src/modules/tools/presentation/routes.py` | `from modules.tools.application.composers...` | intra-module |
| `src/modules/tools/presentation/schemas.py` | `from modules.tools.domain...` | intra-module |

## Cross-Module Dependency Architecture (production code)

```
agent.providers → identity.service.use_cases  [application → other module's service layer]
```

No other production module imports from another module's domain, infra, or presentation.

## Legacy module references found in src

The following modules still reference `ai`, `knowledge`, `runtime` legacy schemas in their models.py via ForeignKey strings (not Python imports):

- `src/modules/agent/infra/database/models.py`: 32 legacy FK references to `ai.*`, `knowledge.*`, `runtime.*`
- `src/modules/metering/infra/models.py`: FK('ai.agents.id')
- `src/modules/observability/infra/models.py`: FK('ai.agents.id'), FK('runtime.sessions.id')
- `src/modules/tools/infra/models.py`: FK('ai.agents.id')

These are physical FK constraints (not Python imports) and are catalogued in `database-ownership.md`.

## Legacy Python imports in tests (for test-only allowlist)

| Test File | Import | Notes |
|---|---|---|
| `tests/architecture/test_add_agent_boundary_architecture_tests.py` | `from modules.ai.domain.entities`, `from modules.knowledge.infra.repositories`, `from modules.runtime.service.ask_use_case` | Test uses legacy module names to verify rejection |
| `tests/architecture/test_agent_boundaries.py` | same pattern | Verifies agent boundary enforcement |
| `tests/architecture/test_shared_boundaries.py` | `from modules.ai.domain.entities`, `from modules.billing.infra.repositories` | Shared layer test |
| `tests/architecture/test_add_legacy_module_allowlist.py` | `from modules.billing.domain.entities`, `from modules.identity.domain.repositories` | Allowlist test |
| `tests/architecture/test_worker_locations.py` | `from modules.runtime.infra.ask_job_worker`, `from modules.metering.infra.models` | Worker location test |
| Various `test_*.py` in `tests/unit/` | intra-module imports | Unit tests |

## Import Pattern Summary

| Pattern | Count | Notes |
|---|---|---|
| Intra-module domain → domain | many | Normal |
| Intra-module application → domain | many | Normal |
| Intra-module application → infra | ~40 composers | Composers wire infra repos + service use_cases + controllers |
| Intra-module infra → domain | many | Normal |
| Intra-module infra → infra | many | Models/repos/mappers cross-refs |
| Intra-module presentation → application | all routes | Normal |
| Intra-module controllers → service use_cases | all controllers | Uses service layer directly |
| Cross-module (agent → identity) | 1 | providers.py |
| Cross-module test imports | ~15 | Architecture tests referencing legacy modules |
| Missing: import_graph.py | 1 | Script not found |

## Key Gap — Service Layer Pattern

All non-agent modules use `service/` directory with `use_cases.py` and `dtos.py`. Composers import directly from `service/use_cases`, and controllers import from `service/use_cases` and `service/dtos`. This differs from agent which has `application/use_cases/` and `application/dtos/` subdirectories.

When moving `service/` → `application/use_cases/` and `application/dtos/`:
- All `from modules.<m>.service.use_cases import ...` must become `from modules.<m>.application.use_cases import ...`
- All `from modules.<m>.service.dtos import ...` must become `from modules.<m>.application.dtos import ...`
- All `from modules.<m>.service.tool_converter import ...` must become `from modules.<m>.application.use_cases.tool_converter import ...`
- All `from modules.<m>.service.providers import ...` (exists in agent) remains in `application/providers.py`
