# Current-to-Target Structure Matrix

**Date:** 2026-06-14
**Branch:** project-rai-playground_module-architecture-standardization
**SHA:** 763ef71

## Notes
- Generated during spec 011 execution.
- `find` (Unix) unavailable; substituted with `Get-ChildItem -Recurse -File | Where-Object { $_.FullName -notmatch '__pycache__' }`.
- Action codes: **keep** (already canonical), **move** (move file to canonical path), **create** (new canonical file needed), **remove** (legacy path to deprecate), **split** (extract into canonical subfiles), **merge** (consolidate into canonical file).

## agent — ALREADY CANONICAL (minor gaps)

| Current Path | Canonical Path | Action |
|---|---|---|
| `src/modules/agent/domain/entities.py` | same | keep |
| `src/modules/agent/domain/enums.py` | same | keep |
| `src/modules/agent/domain/errors.py` | same | keep |
| `src/modules/agent/domain/events.py` | same | keep |
| `src/modules/agent/domain/repositories.py` | same | keep |
| `src/modules/agent/domain/services.py` | same | keep |
| `src/modules/agent/domain/value_objects.py` | same | keep |
| `src/modules/agent/application/composers/*.py` | same | keep |
| `src/modules/agent/application/dtos/ai_dtos.py` | `src/modules/agent/application/dtos/ai_dtos.py` | keep |
| `src/modules/agent/application/dtos/knowledge_dtos.py` | `src/modules/agent/application/dtos/knowledge_dtos.py` | keep |
| `src/modules/agent/application/dtos/runtime_dtos.py` | `src/modules/agent/application/dtos/runtime_dtos.py` | keep |
| `src/modules/agent/application/use_cases/ai_use_cases.py` | `src/modules/agent/application/use_cases/ai_use_cases.py` | keep |
| `src/modules/agent/application/use_cases/ask_agent_stream_service.py` | `src/modules/agent/application/use_cases/ask_agent_stream_service.py` | keep |
| `src/modules/agent/application/use_cases/ask_use_case.py` | `src/modules/agent/application/use_cases/ask_use_case.py` | keep |
| `src/modules/agent/application/use_cases/knowledge_use_cases.py` | `src/modules/agent/application/use_cases/knowledge_use_cases.py` | keep |
| `src/modules/agent/application/use_cases/runtime_use_cases.py` | `src/modules/agent/application/use_cases/runtime_use_cases.py` | keep |
| `src/modules/agent/application/handlers/__init__.py` | `src/modules/agent/application/handlers/` | keep (expand) |
| `src/modules/agent/infra/database/models.py` | same | keep |
| `src/modules/agent/infra/database/repositories.py` | same | keep |
| `src/modules/agent/infra/database/mappers.py` | same | keep |
| `src/modules/agent/infra/database/unit_of_work.py` | same | keep |
| `src/modules/agent/infra/llm/langchain_factory.py` | same | keep |
| `src/modules/agent/infra/llm/providers.py` | same | keep |
| `src/modules/agent/infra/messaging/consumers.py` | same | keep |
| `src/modules/agent/infra/messaging/event_mappers.py` | same | keep |
| `src/modules/agent/infra/messaging/inbox_handlers.py` | same | keep |
| `src/modules/agent/infra/messaging/publishers.py` | same | keep |
| `src/modules/agent/infra/workers/*.py` | same | keep |
| `src/modules/agent/presentation/routes.py` | same | keep |
| `src/modules/agent/presentation/schemas.py` | same | keep |
| `src/modules/agent/presentation/mappers.py` | same | keep |
| `src/modules/agent/presentation/controllers/*.py` | same | keep |

## billing — NEEDS RESTRUCTURE

| Current Path | Canonical Path | Action |
|---|---|---|
| `src/modules/billing/domain/entities.py` | same | keep |
| `src/modules/billing/domain/enums.py` | same | keep |
| `src/modules/billing/domain/errors.py` | same | keep |
| `src/modules/billing/domain/repositories.py` | same | keep |
| (missing) | `src/modules/billing/domain/events.py` | create |
| (missing) | `src/modules/billing/domain/services.py` | create |
| (missing) | `src/modules/billing/domain/value_objects.py` | create |
| `src/modules/billing/service/use_cases.py` | `src/modules/billing/application/use_cases/use_cases.py` | move |
| `src/modules/billing/service/dtos.py` | `src/modules/billing/application/dtos/dtos.py` | move |
| `src/modules/billing/application/composers/*.py` | same | keep |
| `src/modules/billing/infra/models.py` | `src/modules/billing/infra/database/models.py` | move |
| `src/modules/billing/infra/repositories.py` | `src/modules/billing/infra/database/repositories.py` | move |
| `src/modules/billing/infra/mappers.py` | `src/modules/billing/infra/database/mappers.py` | move |
| (missing) | `src/modules/billing/infra/database/unit_of_work.py` | create |
| (missing) | `src/modules/billing/infra/messaging/consumers.py` | create |
| (missing) | `src/modules/billing/infra/messaging/event_mappers.py` | create |
| (missing) | `src/modules/billing/infra/messaging/publishers.py` | create |
| `src/modules/billing/infra/workers/registry.py` | same | keep |
| (missing) | `src/modules/billing/infra/workers/inbox_consumer.py` | create |
| (missing) | `src/modules/billing/infra/workers/inbox_processor.py` | create |
| (missing) | `src/modules/billing/infra/workers/outbox_dispatcher.py` | create |
| `src/modules/billing/presentation/routes.py` | same | keep |
| `src/modules/billing/presentation/schemas.py` | same | keep |
| `src/modules/billing/presentation/controllers/*.py` | same | keep |
| (missing) | `src/modules/billing/presentation/mappers.py` | create |

## core — NEEDS RESTRUCTURE

| Current Path | Canonical Path | Action |
|---|---|---|
| `src/modules/core/domain/entities.py` | same | keep |
| `src/modules/core/domain/enums.py` | same | keep |
| `src/modules/core/domain/errors.py` | same | keep |
| `src/modules/core/domain/repositories.py` | same | keep |
| (missing) | `src/modules/core/domain/events.py` | create |
| (missing) | `src/modules/core/domain/services.py` | create |
| (missing) | `src/modules/core/domain/value_objects.py` | create |
| `src/modules/core/service/use_cases.py` | `src/modules/core/application/use_cases/use_cases.py` | move |
| `src/modules/core/service/dtos.py` | `src/modules/core/application/dtos/dtos.py` | move |
| `src/modules/core/application/composers/*.py` | same | keep |
| `src/modules/core/application/dependencies.py` | same | keep |
| `src/modules/core/infra/models.py` | `src/modules/core/infra/database/models.py` | move |
| `src/modules/core/infra/repositories.py` | `src/modules/core/infra/database/repositories.py` | move |
| `src/modules/core/infra/mappers.py` | `src/modules/core/infra/database/mappers.py` | move |
| (missing) | `src/modules/core/infra/database/unit_of_work.py` | create |
| (missing) | `src/modules/core/infra/messaging/*.py` | create |
| (missing) | `src/modules/core/infra/workers/*.py` | create |
| `src/modules/core/presentation/routes.py` | same | keep |
| `src/modules/core/presentation/schemas.py` | same | keep |
| `src/modules/core/presentation/controllers/*.py` | same | keep |
| `src/modules/core/presentation/mappers.py` | same | keep |

## identity — NEEDS RESTRUCTURE

| Current Path | Canonical Path | Action |
|---|---|---|
| `src/modules/identity/domain/entities.py` | same | keep |
| `src/modules/identity/domain/enums.py` | same | keep |
| `src/modules/identity/domain/errors.py` | same | keep |
| `src/modules/identity/domain/repositories.py` | same | keep |
| (missing) | `src/modules/identity/domain/events.py` | create |
| (missing) | `src/modules/identity/domain/services.py` | create |
| (missing) | `src/modules/identity/domain/value_objects.py` | create |
| `src/modules/identity/service/use_cases.py` | `src/modules/identity/application/use_cases/use_cases.py` | move |
| `src/modules/identity/service/dtos.py` | `src/modules/identity/application/dtos/dtos.py` | move |
| `src/modules/identity/application/composers/*.py` | same | keep |
| `src/modules/identity/infra/models.py` | `src/modules/identity/infra/database/models.py` | move |
| `src/modules/identity/infra/repositories.py` | `src/modules/identity/infra/database/repositories.py` | move |
| `src/modules/identity/infra/mappers.py` | `src/modules/identity/infra/database/mappers.py` | move |
| (missing) | `src/modules/identity/infra/database/unit_of_work.py` | create |
| (missing) | `src/modules/identity/infra/messaging/*.py` | create |
| `src/modules/identity/infra/workers/registry.py` | same | keep |
| (missing) | `src/modules/identity/infra/workers/inbox*outbox*` | create |
| `src/modules/identity/presentation/routes.py` | same | keep |
| `src/modules/identity/presentation/schemas.py` | same | keep |
| `src/modules/identity/presentation/controllers/*.py` | same | keep |
| (missing) | `src/modules/identity/presentation/mappers.py` | create |

## metering — NEEDS RESTRUCTURE

| Current Path | Canonical Path | Action |
|---|---|---|
| `src/modules/metering/domain/entities.py` | same | keep |
| `src/modules/metering/domain/enums.py` | same | keep |
| `src/modules/metering/domain/errors.py` | same | keep |
| `src/modules/metering/domain/repositories.py` | same | keep |
| (missing) | `src/modules/metering/domain/events.py` | create |
| (missing) | `src/modules/metering/domain/services.py` | create |
| (missing) | `src/modules/metering/domain/value_objects.py` | create |
| `src/modules/metering/service/use_cases.py` | `src/modules/metering/application/use_cases/use_cases.py` | move |
| `src/modules/metering/service/dtos.py` | `src/modules/metering/application/dtos/dtos.py` | move |
| `src/modules/metering/application/composers/*.py` | same | keep |
| `src/modules/metering/infra/models.py` | `src/modules/metering/infra/database/models.py` | move |
| `src/modules/metering/infra/repositories.py` | `src/modules/metering/infra/database/repositories.py` | move |
| `src/modules/metering/infra/mappers.py` | `src/modules/metering/infra/database/mappers.py` | move |
| (missing) | `src/modules/metering/infra/database/unit_of_work.py` | create |
| (missing) | `src/modules/metering/infra/messaging/*.py` | create |
| `src/modules/metering/infra/workers/registry.py` | same | keep |
| (missing) | `src/modules/metering/infra/workers/inbox*outbox*` | create |
| `src/modules/metering/presentation/routes.py` | same | keep |
| `src/modules/metering/presentation/schemas.py` | same | keep |
| `src/modules/metering/presentation/controllers/*.py` | same | keep |
| (missing) | `src/modules/metering/presentation/mappers.py` | create |

## observability — NEEDS RESTRUCTURE

| Current Path | Canonical Path | Action |
|---|---|---|
| `src/modules/observability/domain/entities.py` | same | keep |
| `src/modules/observability/domain/enums.py` | same | keep |
| `src/modules/observability/domain/errors.py` | same | keep |
| `src/modules/observability/domain/repositories.py` | same | keep |
| (missing) | `src/modules/observability/domain/events.py` | create |
| (missing) | `src/modules/observability/domain/services.py` | create |
| (missing) | `src/modules/observability/domain/value_objects.py` | create |
| `src/modules/observability/service/use_cases.py` | `src/modules/observability/application/use_cases/use_cases.py` | move |
| `src/modules/observability/service/dtos.py` | `src/modules/observability/application/dtos/dtos.py` | move |
| `src/modules/observability/application/composers/*.py` | same | keep |
| `src/modules/observability/infra/models.py` | `src/modules/observability/infra/database/models.py` | move |
| `src/modules/observability/infra/repositories.py` | `src/modules/observability/infra/database/repositories.py` | move |
| `src/modules/observability/infra/mappers.py` | `src/modules/observability/infra/database/mappers.py` | move |
| (missing) | `src/modules/observability/infra/database/unit_of_work.py` | create |
| (missing) | `src/modules/observability/infra/messaging/*.py` | create |
| `src/modules/observability/infra/workers/registry.py` | same | keep |
| (missing) | `src/modules/observability/infra/workers/inbox*outbox*` | create |
| `src/modules/observability/presentation/routes.py` | same | keep |
| `src/modules/observability/presentation/schemas.py` | same | keep |
| `src/modules/observability/presentation/controllers/*.py` | same | keep |
| (missing) | `src/modules/observability/presentation/mappers.py` | create |

## tools — NEEDS RESTRUCTURE

| Current Path | Canonical Path | Action |
|---|---|---|
| `src/modules/tools/domain/entities.py` | same | keep |
| `src/modules/tools/domain/enums.py` | same | keep |
| `src/modules/tools/domain/errors.py` | same | keep |
| `src/modules/tools/domain/repositories.py` | same | keep |
| (missing) | `src/modules/tools/domain/events.py` | create |
| (missing) | `src/modules/tools/domain/services.py` | create |
| (missing) | `src/modules/tools/domain/value_objects.py` | create |
| `src/modules/tools/service/use_cases.py` | `src/modules/tools/application/use_cases/use_cases.py` | move |
| `src/modules/tools/service/dtos.py` | `src/modules/tools/application/dtos/dtos.py` | move |
| `src/modules/tools/service/tool_converter.py` | `src/modules/tools/application/use_cases/tool_converter.py` | move |
| `src/modules/tools/application/composers/*.py` | same | keep |
| `src/modules/tools/infra/models.py` | `src/modules/tools/infra/database/models.py` | move |
| `src/modules/tools/infra/repositories.py` | `src/modules/tools/infra/database/repositories.py` | move |
| `src/modules/tools/infra/mappers.py` | `src/modules/tools/infra/database/mappers.py` | move |
| (missing) | `src/modules/tools/infra/database/unit_of_work.py` | create |
| (missing) | `src/modules/tools/infra/messaging/*.py` | create |
| `src/modules/tools/infra/workers/registry.py` | same | keep |
| (missing) | `src/modules/tools/infra/workers/inbox*outbox*` | create |
| `src/modules/tools/presentation/routes.py` | same | keep |
| `src/modules/tools/presentation/schemas.py` | same | keep |
| `src/modules/tools/presentation/controllers/*.py` | same | keep |
| `src/modules/tools/presentation/mappers.py` | same | keep |

## Summary

| Module | Status | Files to move | Files to create | Files to keep |
|---|---|---|---|---|
| agent | canonical | 0 | 0 | 82 |
| billing | restructure needed | 6 | 11 | 22 |
| core | restructure needed | 6 | 13 | 26 |
| identity | restructure needed | 6 | 11 | 38 |
| metering | restructure needed | 6 | 11 | 22 |
| observability | restructure needed | 6 | 11 | 22 |
| tools | restructure needed | 7 | 11 | 36 |
