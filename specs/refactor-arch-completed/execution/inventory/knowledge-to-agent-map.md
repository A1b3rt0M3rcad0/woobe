# Knowledge to Agent Migration Map

Spec: `030-map-knowledge-to-agent`
Date: 2026-06-14
Agent: opencode/deepseek-v4-pro

## Summary

| Category | File count | Target layer |
|---|---|---|
| Domain | 5 | `agent/domain` |
| Service (use cases, DTOs) | 3 | `agent/application/use_cases`, `agent/application/dtos` |
| Application/Composers | 14 | `agent/application/composers` |
| Infra (models, repos, mappers) | 4 | `agent/infra/database` |
| Presentation (routes, schemas, mappers) | 4 | `agent/presentation` |
| Presentation/Controllers | 13 | `agent/presentation/controllers` |
| **Total** | **43** | |

## Domain Layer

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/knowledge/domain/__init__.py` | `src/modules/agent/domain/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/knowledge/domain/entities.py` | `src/modules/agent/domain/entities.py` (merge) | domain entities (DocumentCollection, AgentCollection, Document, DocumentChunk, KnowledgeVersion) | runtime.service.ask_use_case (indirect via repos), tests | all /knowledge routes | - | medium — runtime imports repos that use these | test entity instantiation after move |
| `src/modules/knowledge/domain/enums.py` | `src/modules/agent/domain/enums.py` (merge) | domain enums (CollectionStatus, DocumentStatus, ParserType, KnowledgeVersionStatus) | knowledge.service.dtos, knowledge.presentation.schemas | all /knowledge routes | - | low | test enum availability after move |
| `src/modules/knowledge/domain/errors.py` | `src/modules/agent/domain/errors.py` (merge) | domain errors (CollectionNotFoundError, DocumentNotFoundError, ChunkNotFoundError, DuplicateCollectionError, KnowledgeVersionNotFoundError) | knowledge.service.use_cases | - | - | low | test error classes exist after move |
| `src/modules/knowledge/domain/repositories.py` | `src/modules/agent/domain/repositories.py` (merge) | repository interfaces (DocumentCollectionRepository, DocumentRepository, AgentCollectionRepository, DocumentChunkRepository, KnowledgeVersionRepository) | runtime.service.ask_use_case, runtime.service.ask_agent_stream_service | all /knowledge routes | - | high — cross-module consumer | test interface availability after move |

## Application Layer — Composers

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/knowledge/application/__init__.py` | `src/modules/agent/application/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/knowledge/application/composers/__init__.py` | `src/modules/agent/application/composers/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/knowledge/application/composers/attach_collection_composer.py` | `src/modules/agent/application/composers/attach_collection_composer.py` | composer | knowledge.presentation.routes | POST /knowledge/agent-collections | - | low | route handler test |
| `src/modules/knowledge/application/composers/create_collection_composer.py` | `src/modules/agent/application/composers/create_collection_composer.py` | composer | knowledge.presentation.routes | POST /knowledge/collections | - | low | route handler test |
| `src/modules/knowledge/application/composers/create_knowledge_version_composer.py` | `src/modules/agent/application/composers/create_knowledge_version_composer.py` | composer | knowledge.presentation.routes | POST /knowledge/agents/{id}/knowledge-versions | - | low | route handler test |
| `src/modules/knowledge/application/composers/detach_collection_composer.py` | `src/modules/agent/application/composers/detach_collection_composer.py` | composer | knowledge.presentation.routes | DELETE /knowledge/agent-collections/{id} | - | low | route handler test |
| `src/modules/knowledge/application/composers/get_collection_composer.py` | `src/modules/agent/application/composers/get_collection_composer.py` | composer | knowledge.presentation.routes | GET /knowledge/collections/{id} | - | low | route handler test |
| `src/modules/knowledge/application/composers/get_document_composer.py` | `src/modules/agent/application/composers/get_document_composer.py` | composer | knowledge.presentation.routes | GET /knowledge/documents/{id} | - | low | route handler test |
| `src/modules/knowledge/application/composers/list_agent_collections_composer.py` | `src/modules/agent/application/composers/list_agent_collections_composer.py` | composer | knowledge.presentation.routes | GET /knowledge/agent-collections | - | low | route handler test |
| `src/modules/knowledge/application/composers/list_collections_composer.py` | `src/modules/agent/application/composers/list_collections_composer.py` | composer | knowledge.presentation.routes | GET /knowledge/collections | - | low | route handler test |
| `src/modules/knowledge/application/composers/list_documents_composer.py` | `src/modules/agent/application/composers/list_documents_composer.py` | composer | knowledge.presentation.routes | GET /knowledge/documents | - | low | route handler test |
| `src/modules/knowledge/application/composers/list_knowledge_versions_composer.py` | `src/modules/agent/application/composers/list_knowledge_versions_composer.py` | composer | knowledge.presentation.routes | GET /knowledge/agents/{id}/knowledge-versions | - | low | route handler test |
| `src/modules/knowledge/application/composers/search_chunks_composer.py` | `src/modules/agent/application/composers/search_chunks_composer.py` | composer | knowledge.presentation.routes | POST /knowledge/search | - | low | route handler test |
| `src/modules/knowledge/application/composers/upload_document_composer.py` | `src/modules/agent/application/composers/upload_document_composer.py` | composer | knowledge.presentation.routes | POST /knowledge/documents | - | low | route handler test |

## Service Layer (maps to Application)

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/knowledge/service/__init__.py` | `src/modules/agent/application/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/knowledge/service/dtos.py` | `src/modules/agent/application/dtos/knowledge_dtos.py` | DTOs | knowledge.service.use_cases, knowledge.presentation.controllers | all /knowledge routes | - | low | DTO instantiation test |
| `src/modules/knowledge/service/use_cases.py` | `src/modules/agent/application/use_cases/knowledge_use_cases.py` | use cases (12 classes) | knowledge.application.composers, tests/unit/test_knowledge | all /knowledge routes | writes to knowledge.outbox_events | medium — produces events | unit test use case execution |

## Infra Layer — Database

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/knowledge/infra/__init__.py` | `src/modules/agent/infra/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/knowledge/infra/models.py` | `src/modules/agent/infra/database/models.py` (merge) | SQLAlchemy models (DocumentCollectionModel, AgentCollectionModel, DocumentModel, DocumentChunkModel, KnowledgeVersionModel, OutboxEventModel, InboxEventModel) | runtime.infra.ask_job_worker (indirect), migrations/env.py, shared/workers (dynamic) | all /knowledge routes | knowledge.document_collections, knowledge.agent_collections, knowledge.documents, knowledge.document_chunks, knowledge.knowledge_versions, knowledge.outbox_events, knowledge.inbox_events | high — schema rename requires expand-migrate-contract; pgvector dependency | model import test |
| `src/modules/knowledge/infra/mappers.py` | `src/modules/agent/infra/database/mappers.py` (merge) | entity-model mappers (10 functions) | knowledge.infra.repositories | all /knowledge routes | - | low | mapper function test |
| `src/modules/knowledge/infra/repositories.py` | `src/modules/agent/infra/database/repositories.py` (merge) | SQLAlchemy repositories (SQLAlchemyDocumentCollectionRepository, SQLAlchemyDocumentRepository, SQLAlchemyAgentCollectionRepository, SQLAlchemyDocumentChunkRepository, SQLAlchemyKnowledgeVersionRepository, SQLAlchemyOutboxEventWriter) | runtime.infra.ask_job_worker, runtime.application.composers.ask_agent_composer, runtime.service.ask_agent_stream_service | all /knowledge routes | - | high — cross-module consumer imports | repository import test |

## Presentation Layer

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/knowledge/presentation/__init__.py` | `src/modules/agent/presentation/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/knowledge/presentation/routes.py` | `src/modules/agent/presentation/routes.py` (merge) | FastAPI router (12 routes, prefix=/knowledge) | src/main.py (bootstrap) | all 12 /knowledge routes | - | medium — prefix change needs shim | route registration test |
| `src/modules/knowledge/presentation/schemas.py` | `src/modules/agent/presentation/schemas.py` (merge) | Pydantic schemas (11 classes) | knowledge.presentation.controllers | all /knowledge routes | - | low | schema validation test |
| `src/modules/knowledge/presentation/mappers.py` | `src/modules/agent/presentation/mappers.py` (merge) | response mappers (9 functions) | knowledge.presentation.controllers | all /knowledge routes | - | low | mapper test |

## Presentation Layer — Controllers

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/knowledge/presentation/controllers/__init__.py` | `src/modules/agent/presentation/controllers/__init__.py` (merge) | package init | none | - | - | low | import test |
| `src/modules/knowledge/presentation/controllers/attach_collection_controller.py` | `src/modules/agent/presentation/controllers/attach_collection_controller.py` | controller | knowledge.presentation.routes | POST /knowledge/agent-collections | - | low | controller test |
| `src/modules/knowledge/presentation/controllers/create_collection_controller.py` | `src/modules/agent/presentation/controllers/create_collection_controller.py` | controller | knowledge.presentation.routes | POST /knowledge/collections | - | low | controller test |
| `src/modules/knowledge/presentation/controllers/create_knowledge_version_controller.py` | `src/modules/agent/presentation/controllers/create_knowledge_version_controller.py` | controller | knowledge.presentation.routes | POST /knowledge/agents/{id}/knowledge-versions | - | low | controller test |
| `src/modules/knowledge/presentation/controllers/detach_collection_controller.py` | `src/modules/agent/presentation/controllers/detach_collection_controller.py` | controller | knowledge.presentation.routes | DELETE /knowledge/agent-collections/{id} | - | low | controller test |
| `src/modules/knowledge/presentation/controllers/get_collection_controller.py` | `src/modules/agent/presentation/controllers/get_collection_controller.py` | controller | knowledge.presentation.routes | GET /knowledge/collections/{id} | - | low | controller test |
| `src/modules/knowledge/presentation/controllers/get_document_controller.py` | `src/modules/agent/presentation/controllers/get_document_controller.py` | controller | knowledge.presentation.routes | GET /knowledge/documents/{id} | - | low | controller test |
| `src/modules/knowledge/presentation/controllers/list_agent_collections_controller.py` | `src/modules/agent/presentation/controllers/list_agent_collections_controller.py` | controller | knowledge.presentation.routes | GET /knowledge/agent-collections | - | low | controller test |
| `src/modules/knowledge/presentation/controllers/list_collections_controller.py` | `src/modules/agent/presentation/controllers/list_collections_controller.py` | controller | knowledge.presentation.routes | GET /knowledge/collections | - | low | controller test |
| `src/modules/knowledge/presentation/controllers/list_documents_controller.py` | `src/modules/agent/presentation/controllers/list_documents_controller.py` | controller | knowledge.presentation.routes | GET /knowledge/documents | - | low | controller test |
| `src/modules/knowledge/presentation/controllers/list_knowledge_versions_controller.py` | `src/modules/agent/presentation/controllers/list_knowledge_versions_controller.py` | controller | knowledge.presentation.routes | GET /knowledge/agents/{id}/knowledge-versions | - | low | controller test |
| `src/modules/knowledge/presentation/controllers/search_chunks_controller.py` | `src/modules/agent/presentation/controllers/search_chunks_controller.py` | controller | knowledge.presentation.routes | POST /knowledge/search | - | low | controller test |
| `src/modules/knowledge/presentation/controllers/upload_document_controller.py` | `src/modules/agent/presentation/controllers/upload_document_controller.py` | controller | knowledge.presentation.routes | POST /knowledge/documents | - | low | controller test |

## Database Tables (Schema: knowledge → agent)

| Table | Current Schema | Target Schema | Model | FKs intra-module | FKs cross-module (blocker) | Risk | Migration spec |
|---|---|---|---|---|---|---|---|
| document_collections | knowledge | agent | DocumentCollectionModel | - | project_id → core.projects.id | medium | 134 |
| agent_collections | knowledge | agent | AgentCollectionModel | collection_id → knowledge.document_collections.id | agent_id → ai.agents.id (becomes intra-module after consolidation) | medium | 134 |
| documents | knowledge | agent | DocumentModel | collection_id → knowledge.document_collections.id | project_id → core.projects.id | medium | 134 |
| document_chunks | knowledge | agent | DocumentChunkModel | collection_id → knowledge.document_collections.id, document_id → knowledge.documents.id | project_id → core.projects.id | high — pgvector dependency | 134 |
| knowledge_versions | knowledge | agent | KnowledgeVersionModel | - | project_id → core.projects.id, agent_id → ai.agents.id (becomes intra-module) | medium | 134 |
| outbox_events | knowledge | agent | OutboxEventModel | - | - | medium — merge with ai/runtime outbox | 070-076 |
| inbox_events | knowledge | agent | InboxEventModel | - | - | medium — merge with ai/runtime inbox | 070-076 |

## Events Produced

| event_type | aggregate_type | Producer use case | Current schema | Target schema | Routing impact | Risk |
|---|---|---|---|---|---|---|
| `collection.created` | document_collection | CreateCollectionUseCase | knowledge.outbox_events | agent.outbox_events | InboxConsumer routes to "collection" (fails — no such module) | medium — already broken |
| `document.uploaded` | document | UploadDocumentUseCase | knowledge.outbox_events | agent.outbox_events | InboxConsumer routes to "document" (fails — no such module) | medium — already broken |

## External Consumers of Knowledge Module

| Consumer file | Import path | Symbols used | Resolution strategy |
|---|---|---|---|
| `src/modules/runtime/service/ask_use_case.py` | `modules.knowledge.domain.repositories` | AgentCollectionRepository, DocumentChunkRepository | Consolidate into agent domain (specs 040-045) |
| `src/modules/runtime/service/ask_agent_stream_service.py` | `modules.knowledge.domain.repositories` | AgentCollectionRepository, DocumentChunkRepository | Consolidate into agent domain |
| `src/modules/runtime/service/ask_agent_stream_service.py` | `modules.knowledge.infra.repositories` | SQLAlchemyAgentCollectionRepository, SQLAlchemyDocumentChunkRepository | Consolidate into agent infra |
| `src/modules/runtime/infra/ask_job_worker.py` | `modules.knowledge.infra.repositories` | SQLAlchemyAgentCollectionRepository, SQLAlchemyDocumentChunkRepository | Consolidate into agent infra |
| `src/modules/runtime/application/composers/ask_agent_composer.py` | `modules.knowledge.infra.repositories` | SQLAlchemyAgentCollectionRepository, SQLAlchemyDocumentChunkRepository | Consolidate into agent infra |
| `src/main.py` | `modules.knowledge.presentation.routes` | router (as knowledge_router) | Update bootstrap to agent (spec 130-131) |
| `migrations/env.py` | `modules.knowledge.infra.models` | (metadata) | Update to agent (spec 134) |
| `src/shared/workers/outbox_publisher.py` | dynamic: module list includes "knowledge" | OutboxEventModel | Replace with registry (specs 050-063) |
| `src/shared/workers/inbox_dispatcher.py` | dynamic: module list includes "knowledge" | InboxEventModel | Replace with registry (specs 050-063) |
| `tests/unit/test_knowledge/*` | `modules.knowledge.*` | all test imports | Update to agent after move |
| `tests/helpers.py` | `modules.knowledge.domain.entities` | DocumentCollection, Document | Update to agent after move |

## Route Migration Plan

| Current route | Target route | Shim required | Shim removal spec |
|---|---|---|---|
| `/knowledge/collections` | `/agent/collections` | yes — redirect/proxy | 141 |
| `/knowledge/collections/{id}` | `/agent/collections/{id}` | yes — redirect/proxy | 141 |
| `/knowledge/agent-collections` | `/agent/agent-collections` | yes — redirect/proxy | 141 |
| `/knowledge/agent-collections/{id}` | `/agent/agent-collections/{id}` | yes — redirect/proxy | 141 |
| `/knowledge/documents` | `/agent/documents` | yes — redirect/proxy | 141 |
| `/knowledge/documents/{id}` | `/agent/documents/{id}` | yes — redirect/proxy | 141 |
| `/knowledge/search` | `/agent/search` | yes — redirect/proxy | 141 |
| `/knowledge/agents/{id}/knowledge-versions` | `/agent/agents/{id}/knowledge-versions` | yes — redirect/proxy | 141 |

## Risk Summary

| Risk | Severity | Mitigation | Responsible spec |
|---|---|---|---|
| runtime imports 4 concrete repos from knowledge.infra | high | All merge into agent; runtime becomes internal to agent | 040-045 |
| knowledge.agent_collections FK → ai.agents.id (cross knowledge↔ai) | medium | Becomes intra-module FK after consolidation into agent | 134 |
| knowledge.knowledge_versions FK → ai.agents.id (cross knowledge↔ai) | medium | Becomes intra-module FK after consolidation into agent | 134 |
| Schema rename knowledge→agent requires expand-migrate-contract | high | Physical schema change deferred to spec 134 | 134 |
| 12 routes under /knowledge need shim to /agent | medium | Create shim during route migration, remove at spec 141 | 034, 131, 141 |
| shared/workers hard-codes "knowledge" in module list | medium | Replace with registry pattern | 050-063 |
| 2 knowledge events have broken inbox routing (no module prefix) | medium (pre-existing) | Fix during event standardization | 100-109 |
| pgvector Vector(1536) embedding column in document_chunks | medium | Must ensure pgvector extension available during migration | 134 |

## Migration Order

The knowledge module should be migrated layer by layer per specs 031-035:

1. **Spec 031** — Move knowledge domain to agent domain (entities, enums, errors, repositories)
2. **Spec 032** — Move knowledge application to agent application (composers, use cases, DTOs)
3. **Spec 033** — Move knowledge infra to agent infra (models, repositories, mappers)
4. **Spec 034** — Move knowledge presentation to agent presentation (routes, schemas, controllers, mappers)
5. **Spec 035** — Update all knowledge imports to agent imports (shims, tests, bootstrap)

No physical file should be moved until specs 031+ are activated.
