# Runtime da Migração Arquitetural para Agent

## Objetivo da migração

Migrar incrementalmente `src/modules/ai`, `src/modules/knowledge` e `src/modules/runtime` para um único bounded context `src/modules/agent`, preservando o modular monolith, fronteiras internas, rastreabilidade, idempotência e consistência transacional por módulo.

## Decisão arquitetural principal

`ai`, `knowledge` e `runtime` não devem permanecer como módulos independentes no estado final. O contexto correto é `agent`, porque execução de agente, composição de prompt, integração com LLM, uso de knowledge base, sessões, mensagens, releases e ask jobs formam um fluxo operacional único. A separação atual gera acoplamento artificial.

## Regra absoluta de comunicação entre módulos

Toda mudança de estado entre módulos deve ocorrer por eventos persistidos na Outbox do produtor, publicados no RabbitMQ e gravados na Inbox do consumidor antes de ack. O produtor não conhece consumidores. O consumidor não altera tabelas de outro módulo.

## Regra absoluta de ownership de banco e Foreign Keys

No estado final, é proibida qualquer `ForeignKey` física entre tabelas pertencentes a módulos/bounded contexts distintos. Outbox/Inbox é o mecanismo de integração entre módulos; Foreign Keys são permitidas somente dentro do mesmo módulo dono do dado.

Regras objetivas:

- `agent.* -> agent.*`: permitido.
- `billing.* -> billing.*`: permitido.
- `metering.* -> metering.*`: permitido.
- `identity.* -> identity.*`: permitido.
- `agent.* -> billing|metering|identity|core|tools|observability.*`: proibido.
- `billing|metering|identity|core|tools|observability.* -> agent.*`: proibido.
- IDs de outro módulo podem ser armazenados como referências opacas, sem constraint física, sem cascade, sem join para alteração de estado e sem repository/model externo.
- Projeções locais/read models alimentados por eventos são permitidos quando pertencem ao módulo consumidor.
- FKs legadas entre `ai`, `knowledge` e `runtime` são tratadas como dívida de migração e devem ser consolidadas dentro de `agent`; após a consolidação, nenhuma FK deve apontar para schemas legados `ai`, `knowledge` ou `runtime`.

A validação final deve falhar se existir `ForeignKey("<schema_externo>.<tabela>.id")`, `ForeignKey('<schema_externo>.<tabela>.id')` ou constraint equivalente entre módulos.

Toda alteração de estado de um módulo só pode ocorrer por API pública do próprio módulo ou por processamento de evento persistido na Inbox do próprio módulo. Nenhum módulo pode importar repository, model, entity, service, use case ou infra de outro módulo para alterar estado.

## Fluxo obrigatório Outbox/Inbox

1. O módulo altera somente seu próprio estado.
2. Na mesma transação, a application layer persiste Outbox do próprio módulo via UoW.
3. O dispatcher do próprio módulo publica no RabbitMQ usando publisher confirms.
4. O dispatcher marca Outbox como published somente após confirmação do broker.
5. O consumer do módulo interessado recebe a mensagem, persiste na Inbox própria e só então faz ack.
6. O processor do módulo consome Inbox pendente, chama handler/use case interno e atualiza estado, Inbox e eventual nova Outbox na mesma transação.

## Papel do Unit of Work

O UoW coordena somente repositories, Outbox e Inbox do próprio módulo. UoW não é serviço de domínio e não atravessa fronteiras de módulo.

## Regra sobre workers

`shared/workers` contém apenas infraestrutura genérica. Workers concretos ficam em `src/modules/<module>/infra/workers`. O runner central apenas descobre registries de módulos e executa workers registrados; ele não conhece eventos de negócio, filas, bindings ou handlers específicos.

## Fora de escopo

- Microservices.
- Separar `ai`, `knowledge` e `runtime` em outros bounded contexts.
- Criar comunicação síncrona direta entre módulos para mudança de estado.
- Mover domínio para `shared`.
- Remoção big bang dos módulos legados.

## Estado atual da migração

Status: `in_progress`. Spec 000 (ADR) concluída em 2026-06-12. Spec 001 (architecture rules modular monolith boundaries) concluída em 2026-06-12. Spec 002 (agent target directory structure) concluída em 2026-06-13. Spec 003 (create current repository inventory) concluída em 2026-06-13. Spec 004 (create current import dependency map) concluída em 2026-06-13. Spec 005 (create current database ownership map) concluída em 2026-06-13. Spec 006 (create current api route map) concluída em 2026-06-13. Spec 007 (create current event catalog) concluída em 2026-06-13. Spec 008 (create current worker inventory) concluída em 2026-06-13. Spec 009 (create migration risk register) concluída em 2026-06-13. Spec 010 (create agent module skeleton) concluída em 2026-06-13. Spec 011 (create agent domain layer skeleton) concluída em 2026-06-13. Spec 012 (create agent application layer skeleton) concluída em 2026-06-13. Spec 013 (create agent infra layer skeleton) concluída em 2026-06-13. Spec 014 (create agent presentation layer skeleton) concluída em 2026-06-13. Spec 015 (add temporary architecture boundary tests) concluída em 2026-06-13. Spec 016 (add shared layer architecture tests) concluída em 2026-06-13. Spec 017 (add worker location architecture tests) concluída em 2026-06-13. Spec 018 (add agent boundary architecture tests) concluída em 2026-06-13. Spec 019 (add legacy module allowlist) concluída em 2026-06-13. Spec 020 (map ai to agent) concluída em 2026-06-13. Spec 021 (move ai domain to agent domain) concluída em 2026-06-13. Spec 022 (move ai application to agent application) concluída em 2026-06-13.

Estado preliminar observado no ProjectRAI em 2026-06-12:

- `src/main.py` registra diretamente os routers `modules.ai`, `modules.knowledge` e `modules.runtime`.
- `src/workers/runner.py` instancia `OutboxPublisherWorker`, `InboxConsumerWorker`, `InboxDispatcherWorker` e `AskJobWorker` diretamente.
- `src/workers/dispatcher.py` contém handlers por evento de negócio e conhece eventos de `identity`, `core`, `ai`, `knowledge` e `metering`.
- `src/shared/workers/outbox_publisher.py` e `src/shared/workers/inbox_dispatcher.py` mantêm listas fixas de módulos, incluindo `ai`, `knowledge` e `runtime`.
- `src/shared/workers/inbox_consumer.py` roteia eventos pelo primeiro segmento do `event_type`, usando uma queue global `projectrai.inbox` e import dinâmico de models do produtor.
- `src/modules/runtime/service/ask_use_case.py` importa diretamente domínio/repositórios de `ai`, `knowledge`, `metering` e `observability`.
- `src/modules/runtime/infra/ask_job_worker.py` monta um caso de uso com repositórios de `ai`, `knowledge`, `runtime`, `metering` e `observability` sob um UoW compartilhado.
- `src/modules/ai/infra/models.py`, `src/modules/knowledge/infra/models.py` e `src/modules/runtime/infra/models.py` têm schemas separados e Outbox/Inbox próprias.
- `migrations/env.py` importa explicitamente models de `ai`, `knowledge` e `runtime` para metadata do Alembic.


## Status das specs

| Spec | Status | Data | Arquivos alterados | Pendências | Próxima recomendada |
|---|---|---|---|---|---|
| 000-architecture-decision-record-agent-bounded-context | completed | 2026-06-12 | tests/architecture/__init__.py, tests/architecture/test_architecture_decision_record_agent_bounded_context.py | - | 001-architecture-rules-modular-monolith-boundaries.md |
| 001-architecture-rules-modular-monolith-boundaries | completed | 2026-06-12 | tests/architecture/test_architecture_rules_modular_monolith_boundaries.py | - | 002-agent-target-directory-structure.md |
| 002-agent-target-directory-structure | completed | 2026-06-13 | tests/architecture/test_agent_target_directory_structure.py | - | 003-create-current-repository-inventory.md |
| 003-create-current-repository-inventory | completed | 2026-06-13 | specs/execution/inventory/files.md, tests/architecture/test_specs_inventory_outputs.py | - | 004-create-current-import-dependency-map.md |
| 004-create-current-import-dependency-map | completed | 2026-06-13 | specs/execution/inventory/imports.md, tests/architecture/test_specs_inventory_outputs.py | - | 005-create-current-database-ownership-map.md |
| 005-create-current-database-ownership-map | completed | 2026-06-13 | specs/execution/inventory/database-ownership.md, tests/architecture/test_specs_inventory_outputs.py | - | 006-create-current-api-route-map.md |
| 006-create-current-api-route-map | completed | 2026-06-13 | specs/execution/inventory/routes.md, tests/architecture/test_specs_inventory_outputs.py | - | 007-create-current-event-catalog.md |
| 007-create-current-event-catalog | completed | 2026-06-13 | specs/execution/inventory/events.md, tests/architecture/test_specs_inventory_outputs.py | - | 008-create-current-worker-inventory.md |
| 008-create-current-worker-inventory | completed | 2026-06-13 | specs/execution/inventory/workers.md, tests/architecture/test_specs_inventory_outputs.py | - | 009-create-migration-risk-register.md |
| 009-create-migration-risk-register | completed | 2026-06-13 | specs/execution/risks.md, tests/architecture/test_specs_inventory_outputs.py | - | 010-create-agent-module-skeleton.md |
| 010-create-agent-module-skeleton | completed | 2026-06-13 | src/modules/agent/**/__init__.py (14 files), tests/architecture/test_create_agent_module_skeleton.py | - | 011-create-agent-domain-layer-skeleton.md |
| 011-create-agent-domain-layer-skeleton | completed | 2026-06-13 | src/modules/agent/domain/{entities,value_objects,events,enums,errors,repositories,services}.py, tests/architecture/test_create_agent_domain_layer_skeleton.py | - | 012-create-agent-application-layer-skeleton.md |
| 012-create-agent-application-layer-skeleton | completed | 2026-06-13 | tests/architecture/test_create_agent_application_layer_skeleton.py | - | 013-create-agent-infra-layer-skeleton.md |
| 013-create-agent-infra-layer-skeleton | completed | 2026-06-13 | src/modules/agent/infra/{database,llm,messaging,workers}/*.py, tests/architecture/test_create_agent_infra_layer_skeleton.py | - | 014-create-agent-presentation-layer-skeleton.md |
| 014-create-agent-presentation-layer-skeleton | completed | 2026-06-13 | src/modules/agent/presentation/{routes,schemas,mappers}.py, tests/architecture/test_create_agent_presentation_layer_skeleton.py | - | 015-add-temporary-architecture-boundary-tests.md |
| 015-add-temporary-architecture-boundary-tests | completed | 2026-06-13 | tests/architecture/test_module_boundaries.py, tests/architecture/test_shared_boundaries.py, tests/architecture/test_worker_locations.py, tests/architecture/test_agent_boundaries.py, tests/architecture/legacy_import_allowlist.yaml | - | 016-add-shared-layer-architecture-tests.md |
| 016-add-shared-layer-architecture-tests | completed | 2026-06-13 | tests/architecture/test_add_shared_layer_architecture_tests.py | - | 017-add-worker-location-architecture-tests.md |
| 017-add-worker-location-architecture-tests | completed | 2026-06-13 | tests/architecture/test_add_worker_location_architecture_tests.py | - | 018-add-agent-boundary-architecture-tests.md |
| 018-add-agent-boundary-architecture-tests | completed | 2026-06-13 | tests/architecture/test_add_agent_boundary_architecture_tests.py | - | 019-add-legacy-module-allowlist.md |
| 019-add-legacy-module-allowlist | completed | 2026-06-13 | tests/architecture/test_add_legacy_module_allowlist.py | - | 020-map-ai-to-agent.md |
| 020-map-ai-to-agent | completed | 2026-06-13 | specs/execution/inventory/ai-to-agent-map.md, tests/architecture/test_map_ai_to_agent.py | - | 021-move-ai-domain-to-agent-domain.md |
| 021-move-ai-domain-to-agent-domain | completed | 2026-06-13 | src/modules/agent/domain/{entities,enums,errors,repositories}.py, src/modules/ai/domain/{entities,enums,errors,repositories}.py (shims), tests/architecture/test_move_ai_domain_to_agent_domain.py, tests/architecture/legacy_import_allowlist.yaml | - | 022-move-ai-application-to-agent-application.md |
| 022-move-ai-application-to-agent-application | completed | 2026-06-13 | src/modules/agent/application/{dtos/ai_dtos.py,use_cases/ai_use_cases.py,composers/*.py}, src/modules/ai/{service,application/composers}/*.py (shims), tests/architecture/test_move_ai_application_to_agent_application.py, tests/architecture/{test_agent_boundaries.py,test_add_agent_boundary_architecture_tests.py,legacy_import_allowlist.yaml} | - | 023-move-ai-infra-llm-to-agent-infra-llm.md |
| 023-move-ai-infra-llm-to-agent-infra-llm | pending | 2026-06-12 | - | executar spec | 024-move-ai-presentation-to-agent-presentation.md |
| 024-move-ai-presentation-to-agent-presentation | pending | 2026-06-12 | - | executar spec | 025-update-ai-imports-to-agent-imports.md |
| 025-update-ai-imports-to-agent-imports | pending | 2026-06-12 | - | executar spec | - |
| 030-map-knowledge-to-agent | pending | 2026-06-12 | - | executar spec | 031-move-knowledge-domain-to-agent-domain.md |
| 031-move-knowledge-domain-to-agent-domain | pending | 2026-06-12 | - | executar spec | 032-move-knowledge-application-to-agent-application.md |
| 032-move-knowledge-application-to-agent-application | pending | 2026-06-12 | - | executar spec | 033-move-knowledge-infra-to-agent-infra.md |
| 033-move-knowledge-infra-to-agent-infra | pending | 2026-06-12 | - | executar spec | 034-move-knowledge-presentation-to-agent-presentation.md |
| 034-move-knowledge-presentation-to-agent-presentation | pending | 2026-06-12 | - | executar spec | 035-update-knowledge-imports-to-agent-imports.md |
| 035-update-knowledge-imports-to-agent-imports | pending | 2026-06-12 | - | executar spec | - |
| 040-map-runtime-to-agent | pending | 2026-06-12 | - | executar spec | 041-move-runtime-domain-to-agent-domain.md |
| 041-move-runtime-domain-to-agent-domain | pending | 2026-06-12 | - | executar spec | 042-move-runtime-application-to-agent-application.md |
| 042-move-runtime-application-to-agent-application | pending | 2026-06-12 | - | executar spec | 043-move-runtime-infra-to-agent-infra.md |
| 043-move-runtime-infra-to-agent-infra | pending | 2026-06-12 | - | executar spec | 044-move-runtime-presentation-to-agent-presentation.md |
| 044-move-runtime-presentation-to-agent-presentation | pending | 2026-06-12 | - | executar spec | 045-update-runtime-imports-to-agent-imports.md |
| 045-update-runtime-imports-to-agent-imports | pending | 2026-06-12 | - | executar spec | - |
| 050-create-shared-worker-contracts | pending | 2026-06-12 | - | executar spec | 051-create-shared-outbox-dispatcher-base.md |
| 051-create-shared-outbox-dispatcher-base | pending | 2026-06-12 | - | executar spec | 052-create-shared-inbox-consumer-base.md |
| 052-create-shared-inbox-consumer-base | pending | 2026-06-12 | - | executar spec | 053-create-shared-inbox-processor-base.md |
| 053-create-shared-inbox-processor-base | pending | 2026-06-12 | - | executar spec | 054-create-shared-worker-runner.md |
| 054-create-shared-worker-runner | pending | 2026-06-12 | - | executar spec | 055-create-shared-worker-registry-contract.md |
| 055-create-shared-worker-registry-contract | pending | 2026-06-12 | - | executar spec | - |
| 060-move-root-workers-to-shared-workers | pending | 2026-06-12 | - | executar spec | 061-remove-domain-worker-implementation-from-src-workers.md |
| 061-remove-domain-worker-implementation-from-src-workers | pending | 2026-06-12 | - | executar spec | 062-create-module-worker-registry-pattern.md |
| 062-create-module-worker-registry-pattern | pending | 2026-06-12 | - | executar spec | 063-wire-central-runner-to-module-worker-registries.md |
| 063-wire-central-runner-to-module-worker-registries | pending | 2026-06-12 | - | executar spec | - |
| 070-create-agent-outbox-model-and-repository | pending | 2026-06-12 | - | executar spec | 071-create-agent-inbox-model-and-repository.md |
| 071-create-agent-inbox-model-and-repository | pending | 2026-06-12 | - | executar spec | 072-create-agent-event-contracts.md |
| 072-create-agent-event-contracts | pending | 2026-06-12 | - | executar spec | 073-create-agent-event-mappers.md |
| 073-create-agent-event-mappers | pending | 2026-06-12 | - | executar spec | 074-create-agent-unit-of-work.md |
| 074-create-agent-unit-of-work | pending | 2026-06-12 | - | executar spec | 075-create-agent-outbox-database-migration.md |
| 075-create-agent-outbox-database-migration | pending | 2026-06-12 | - | executar spec | 076-create-agent-inbox-database-migration.md |
| 076-create-agent-inbox-database-migration | pending | 2026-06-12 | - | executar spec | 077-create-agent-outbox-status-transition-policy.md |
| 077-create-agent-outbox-status-transition-policy | pending | 2026-06-12 | - | executar spec | 078-create-agent-inbox-status-transition-policy.md |
| 078-create-agent-inbox-status-transition-policy | pending | 2026-06-12 | - | executar spec | 079-create-agent-outbox-inbox-locking-policy.md |
| 079-create-agent-outbox-inbox-locking-policy | pending | 2026-06-12 | - | executar spec | 080-implement-agent-outbox-dispatcher.md |
| 080-implement-agent-outbox-dispatcher | pending | 2026-06-12 | - | executar spec | 081-implement-agent-rabbitmq-publisher.md |
| 081-implement-agent-rabbitmq-publisher | pending | 2026-06-12 | - | executar spec | 082-implement-agent-inbox-consumer.md |
| 082-implement-agent-inbox-consumer | pending | 2026-06-12 | - | executar spec | 083-implement-agent-inbox-processor.md |
| 083-implement-agent-inbox-processor | pending | 2026-06-12 | - | executar spec | 084-implement-agent-inbox-handlers.md |
| 084-implement-agent-inbox-handlers | pending | 2026-06-12 | - | executar spec | 085-implement-agent-worker-registry.md |
| 085-implement-agent-worker-registry | pending | 2026-06-12 | - | executar spec | - |
| 090-create-billing-worker-structure | pending | 2026-06-12 | - | executar spec | 091-create-metering-worker-structure.md |
| 091-create-metering-worker-structure | pending | 2026-06-12 | - | executar spec | 092-create-identity-worker-structure.md |
| 092-create-identity-worker-structure | pending | 2026-06-12 | - | executar spec | 093-create-tools-worker-structure.md |
| 093-create-tools-worker-structure | pending | 2026-06-12 | - | executar spec | 094-create-observability-worker-structure.md |
| 094-create-observability-worker-structure | pending | 2026-06-12 | - | executar spec | - |
| 100-standardize-module-outbox-pattern | pending | 2026-06-12 | - | executar spec | 101-standardize-module-inbox-pattern.md |
| 101-standardize-module-inbox-pattern | pending | 2026-06-12 | - | executar spec | 102-standardize-event-envelope.md |
| 102-standardize-event-envelope | pending | 2026-06-12 | - | executar spec | 103-standardize-event-idempotency.md |
| 103-standardize-event-idempotency | pending | 2026-06-12 | - | executar spec | 104-standardize-event-retry-policy.md |
| 104-standardize-event-retry-policy | pending | 2026-06-12 | - | executar spec | 105-standardize-dead-letter-policy.md |
| 105-standardize-dead-letter-policy | pending | 2026-06-12 | - | executar spec | 106-standardize-rabbitmq-topology.md |
| 106-standardize-rabbitmq-topology | pending | 2026-06-12 | - | executar spec | 107-standardize-event-versioning-policy.md |
| 107-standardize-event-versioning-policy | pending | 2026-06-12 | - | executar spec | 108-standardize-event-observability-and-tracing.md |
| 108-standardize-event-observability-and-tracing | pending | 2026-06-12 | - | executar spec | 109-standardize-event-compatibility-policy.md |
| 109-standardize-event-compatibility-policy | pending | 2026-06-12 | - | executar spec | 110-update-import-boundary-rules.md |
| 110-update-import-boundary-rules | pending | 2026-06-12 | - | executar spec | 111-add-architecture-tests-for-module-boundaries.md |
| 111-add-architecture-tests-for-module-boundaries | pending | 2026-06-12 | - | executar spec | 112-add-architecture-tests-for-shared-layer.md |
| 112-add-architecture-tests-for-shared-layer | pending | 2026-06-12 | - | executar spec | 113-add-architecture-tests-for-workers.md |
| 113-add-architecture-tests-for-workers | pending | 2026-06-12 | - | executar spec | 114-add-architecture-tests-for-agent-module.md |
| 114-add-architecture-tests-for-agent-module | pending | 2026-06-12 | - | executar spec | - |
| 120-add-agent-unit-tests | pending | 2026-06-12 | - | executar spec | 121-add-agent-integration-tests.md |
| 121-add-agent-integration-tests | pending | 2026-06-12 | - | executar spec | 122-add-outbox-dispatcher-tests.md |
| 122-add-outbox-dispatcher-tests | pending | 2026-06-12 | - | executar spec | 123-add-inbox-consumer-tests.md |
| 123-add-inbox-consumer-tests | pending | 2026-06-12 | - | executar spec | 124-add-inbox-processor-tests.md |
| 124-add-inbox-processor-tests | pending | 2026-06-12 | - | executar spec | 125-add-idempotency-tests.md |
| 125-add-idempotency-tests | pending | 2026-06-12 | - | executar spec | 126-add-unit-of-work-transaction-tests.md |
| 126-add-unit-of-work-transaction-tests | pending | 2026-06-12 | - | executar spec | 127-add-rabbitmq-publisher-confirm-tests.md |
| 127-add-rabbitmq-publisher-confirm-tests | pending | 2026-06-12 | - | executar spec | 128-add-inbox-deduplication-concurrency-tests.md |
| 128-add-inbox-deduplication-concurrency-tests | pending | 2026-06-12 | - | executar spec | 129-add-outbox-dispatch-concurrency-tests.md |
| 129-add-outbox-dispatch-concurrency-tests | pending | 2026-06-12 | - | executar spec | 130-update-application-bootstrap.md |
| 130-update-application-bootstrap | pending | 2026-06-12 | - | executar spec | 131-update-api-routes-to-agent.md |
| 131-update-api-routes-to-agent | pending | 2026-06-12 | - | executar spec | 132-update-dependency-injection-bindings.md |
| 132-update-dependency-injection-bindings | pending | 2026-06-12 | - | executar spec | 133-update-settings-and-config.md |
| 133-update-settings-and-config | pending | 2026-06-12 | - | executar spec | 134-update-alembic-or-database-migrations.md |
| 134-update-alembic-or-database-migrations | pending | 2026-06-12 | - | executar spec | - |
| 140-deprecate-ai-module | pending | 2026-06-12 | - | executar spec | 141-deprecate-knowledge-module.md |
| 141-deprecate-knowledge-module | pending | 2026-06-12 | - | executar spec | 142-deprecate-runtime-module.md |
| 142-deprecate-runtime-module | pending | 2026-06-12 | - | executar spec | 143-remove-legacy-ai-module.md |
| 143-remove-legacy-ai-module | pending | 2026-06-12 | - | executar spec | 144-remove-legacy-knowledge-module.md |
| 144-remove-legacy-knowledge-module | pending | 2026-06-12 | - | executar spec | 145-remove-legacy-runtime-module.md |
| 145-remove-legacy-runtime-module | pending | 2026-06-12 | - | executar spec | - |
| 150-final-cleanup-imports | pending | 2026-06-12 | - | executar spec | 151-final-cleanup-dead-code.md |
| 151-final-cleanup-dead-code | pending | 2026-06-12 | - | executar spec | 152-final-cleanup-src-workers.md |
| 152-final-cleanup-src-workers | pending | 2026-06-12 | - | executar spec | 153-final-architecture-validation.md |
| 153-final-architecture-validation | pending | 2026-06-12 | - | executar spec | 154-final-migration-report.md |
| 154-final-migration-report | pending | 2026-06-12 | - | executar spec | - |

## Specs executadas

| Spec | Data | Agente | Resultado | Arquivos alterados |
|---|---|---|---|---|
| 000-architecture-decision-record-agent-bounded-context | 2026-06-12 | opencode/deepseek-v4-pro | completed | tests/architecture/__init__.py, tests/architecture/test_architecture_decision_record_agent_bounded_context.py |
| 001-architecture-rules-modular-monolith-boundaries | 2026-06-12 | opencode/deepseek-v4-pro | completed | tests/architecture/test_architecture_rules_modular_monolith_boundaries.py |
| 002-agent-target-directory-structure | 2026-06-13 | opencode/deepseek-v4-pro | completed | tests/architecture/test_agent_target_directory_structure.py |
| 003-create-current-repository-inventory | 2026-06-13 | opencode/deepseek-v4-pro | completed | specs/execution/inventory/files.md, tests/architecture/test_specs_inventory_outputs.py |
| 004-create-current-import-dependency-map | 2026-06-13 | opencode/deepseek-v4-pro | completed | specs/execution/inventory/imports.md, tests/architecture/test_specs_inventory_outputs.py |
| 005-create-current-database-ownership-map | 2026-06-13 | opencode/deepseek-v4-pro | completed | specs/execution/inventory/database-ownership.md, tests/architecture/test_specs_inventory_outputs.py |
| 006-create-current-api-route-map | 2026-06-13 | opencode/deepseek-v4-pro | completed | specs/execution/inventory/routes.md, tests/architecture/test_specs_inventory_outputs.py |
| 007-create-current-event-catalog | 2026-06-13 | opencode/deepseek-v4-pro | completed | specs/execution/inventory/events.md, tests/architecture/test_specs_inventory_outputs.py |
| 008-create-current-worker-inventory | 2026-06-13 | opencode/deepseek-v4-pro | completed | specs/execution/inventory/workers.md, tests/architecture/test_specs_inventory_outputs.py |
| 009-create-migration-risk-register | 2026-06-13 | opencode/deepseek-v4-pro | completed | specs/execution/risks.md, tests/architecture/test_specs_inventory_outputs.py |
| 010-create-agent-module-skeleton | 2026-06-13 | opencode/deepseek-v4-pro | completed | src/modules/agent/**/__init__.py (14 files), tests/architecture/test_create_agent_module_skeleton.py |
| 011-create-agent-domain-layer-skeleton | 2026-06-13 | opencode/deepseek-v4-pro | completed | src/modules/agent/domain/{entities,value_objects,events,enums,errors,repositories,services}.py, tests/architecture/test_create_agent_domain_layer_skeleton.py |
| 012-create-agent-application-layer-skeleton | 2026-06-13 | opencode/deepseek-v4-pro | completed | tests/architecture/test_create_agent_application_layer_skeleton.py |
| 013-create-agent-infra-layer-skeleton | 2026-06-13 | opencode/deepseek-v4-pro | completed | src/modules/agent/infra/{database,llm,messaging,workers}/*.py, tests/architecture/test_create_agent_infra_layer_skeleton.py |
| 014-create-agent-presentation-layer-skeleton | 2026-06-13 | opencode/deepseek-v4-pro | completed | src/modules/agent/presentation/{routes,schemas,mappers}.py, tests/architecture/test_create_agent_presentation_layer_skeleton.py |
| 015-add-temporary-architecture-boundary-tests | 2026-06-13 | opencode/deepseek-v4-pro | completed | tests/architecture/test_module_boundaries.py, tests/architecture/test_shared_boundaries.py, tests/architecture/test_worker_locations.py, tests/architecture/test_agent_boundaries.py, tests/architecture/legacy_import_allowlist.yaml |
| 016-add-shared-layer-architecture-tests | 2026-06-13 | opencode/deepseek-v4-pro | completed | tests/architecture/test_add_shared_layer_architecture_tests.py |
| 017-add-worker-location-architecture-tests | 2026-06-13 | opencode/deepseek-v4-pro | completed | tests/architecture/test_add_worker_location_architecture_tests.py |
| 018-add-agent-boundary-architecture-tests | 2026-06-13 | opencode/deepseek-v4-pro | completed | tests/architecture/test_add_agent_boundary_architecture_tests.py |
| 019-add-legacy-module-allowlist | 2026-06-13 | opencode/deepseek-v4-pro | completed | tests/architecture/test_add_legacy_module_allowlist.py |
| 020-map-ai-to-agent | 2026-06-13 | opencode/deepseek-v4-pro | completed | specs/execution/inventory/ai-to-agent-map.md, tests/architecture/test_map_ai_to_agent.py |
| 021-move-ai-domain-to-agent-domain | 2026-06-13 | opencode/deepseek-v4-pro | completed | src/modules/agent/domain/{entities,enums,errors,repositories}.py, src/modules/ai/domain/{entities,enums,errors,repositories}.py (shims), tests/architecture/test_move_ai_domain_to_agent_domain.py, tests/architecture/legacy_import_allowlist.yaml |
| 022-move-ai-application-to-agent-application | 2026-06-13 | opencode/deepseek-v4-pro | completed | src/modules/agent/application/{dtos/ai_dtos.py,use_cases/ai_use_cases.py,composers/*.py (25 files)}, src/modules/ai/{service/dtos.py,service/use_cases.py,application/composers/*.py (25 files)} (shims), tests/architecture/test_move_ai_application_to_agent_application.py, tests/architecture/{test_agent_boundaries.py,test_add_agent_boundary_architecture_tests.py,legacy_import_allowlist.yaml} |

## Specs pendentes

Todas as specs listadas no MANIFEST estão pendentes.

## Decisões tomadas durante a execução

| Data | Decisão | Motivo | Impacto | Reversível? |
|---|---|---|---|---|
| 2026-06-12 | Unificar `ai`, `knowledge` e `runtime` em `agent` | O runtime depende diretamente de IA e conhecimento; os três representam o mesmo domínio operacional | Reorganização de módulos, rotas, imports, schemas e workers | Sim, enquanto os shims estiverem ativos; não após contract final |
| 2026-06-12 | Manter modular monolith | O objetivo é reforçar fronteiras internas sem custo operacional de microservices | Comunicação interna por eventos e UoW por módulo | Sim |
| 2026-06-12 | Workers concretos por módulo | Evita regra de negócio em runner/global workers | `src/workers` removido no estado final | Sim durante migração |
| 2026-06-13 | TransactionalHandler permitido em shared | Classe genérica de infraestrutura (não domain logic); test_shared_boundaries exclui classes com prefixos base/abstract/transactional/generic | Nenhum impacto arquitetural | Sim |
| 2026-06-13 | Shims de depreciação em ai/domain delegando para agent/domain | Manter compatibilidade com runtime e demais consumidores durante migração incremental; warnings emitidos no import | ai→agent no allowlist; remoção na spec 140 | Sim, até spec 140 |
| 2026-06-13 | Agent boundary tests atualizados para respeitar allowlist | Composers do agent importam temporariamente de modules.ai.infra e modules.ai.presentation (não migrados até specs 023-024); tests devem usar allowlist para evitar falsos positivos | Testes de fronteira do agent consultam legacy_import_allowlist.yaml para scope module_boundaries | Sim, até spec 024 |
| 2026-06-13 | Shims de depreciação em ai/service e ai/application/composers delegando para agent/application | Manter compatibilidade com ai.presentation.routes (não migrada até spec 024) e testes legados | ai→agent no allowlist; remoção na spec 140 | Sim, até spec 140 |

## Riscos ativos

| Risco | Severidade | Spec origem | Mitigação | Status |
|---|---|---|---|---|
| Imports cruzados diretos em `runtime` para `ai`, `knowledge`, `metering` e `observability` | alta | 004, 040, 110 | Inventário, allowlist temporária, migração para `agent`, integração com outros módulos via Inbox | aberto |
| UoW compartilhado coordenando repositories de vários módulos | crítica | 074, 126 | Criar `AgentUnitOfWork`; remover coordenação cross-module | aberto |
| Workers globais conhecendo módulos e eventos de negócio | alta | 008, 050-063, 080-085 | Base genérica em shared; workers concretos por módulo | aberto |
| Schemas `ai`, `knowledge`, `runtime` separados | média | 005, 134 | Expand-migrate-contract para schema/tabelas `agent` | aberto |
| 33 FKs físicas cross-module detectadas | alta | 005, 134 | Converter para colunas *_id opacas sem constraint; spec 134 responsável | aberto |
| observability.traces.session_id → runtime.sessions.id (cross-module após migração) | média | 005, 134 | Remover FK física; manter como referência opaca ou projeção via eventos | aberto |
| Event types inconsistentes sem envelope versionado completo | alta | 007, 102-109 | Padronizar envelope, idempotency_key, correlation_id e causation_id | aberto |
| InboxConsumer routing quebrado para 19/27 event_types | crítica | 007, 100-109 | event_type sem prefixo de módulo faz `_module_for_event_type()` rotear para módulo inexistente; eventos nunca chegam ao Inbox | aberto |
| Dispatcher handler keys não correspondem aos event_types reais | alta | 007, 100-109 | 4/5 handlers registrados com chave diferente do event_type produzido; handlers nunca disparam | aberto |
| Runtime produz evento `usage_event.recorded` de domínio do metering | alta | 007, 040-045, 074 | ask_use_case.py:928, ask_agent_stream_service.py:1062 escrevem evento de metering no outbox de runtime | aberto |
| Runner importa AskJobWorker diretamente de `modules.runtime.infra` | alta | 008, 054, 063 | `src/workers/runner.py:13` — cross-module import de infra interna | aberto |
| AskJobWorker não herda BaseWorker | média | 008, 085 | `src/modules/runtime/infra/ask_job_worker.py:35` — não é compatível com contratos genéricos de worker | aberto |
| InboxConsumerWorker silencia erros para módulos sem InboxEventModel | alta | 008, 050-055 | `src/shared/workers/inbox_consumer.py:39-40` — ImportError/AttributeError ignorados, eventos perdidos sem log | aberto |

## Inconsistências encontradas

- `src/workers/dispatcher.py` contém handlers de negócio em pacote global.
- `src/shared/workers/outbox_publisher.py` conhece módulos concretos.
- `src/shared/workers/inbox_consumer.py` consome `#` em queue global e infere módulo pelo produtor.
- `AskJobWorker` monta use case com repositories de múltiplos módulos.
- `AskAgentUseCase` persiste metering e observability diretamente em vez de publicar eventos para consumidores próprios.
- `tests/unit/test_core` e `tests/unit/test_identity` não possuem `__init__.py`, causando erros de coleção no pytest (pré-existente).
- `ruff check src tests` reporta 29 erros pré-existentes (F401, F821, F841) em módulos legados.
- 19/27 event_types não possuem prefixo de módulo; InboxConsumer roteia pelo primeiro segmento e falha silenciosamente para módulos inexistentes.
- Dispatcher handler keys (`identity.organization_created`, `core.project_created`, `ai.agent_created`, `metering.usage_recorded`) não correspondem aos event_types produzidos (`organization.created`, `project.created`, `agent.created`, `usage_event.recorded`).
- Envelope publicado no RabbitMQ não contém timestamp, producer_module, idempotency_key ou schema_version.
- Queue global `projectrai.inbox` com binding `#` recebe todos os eventos sem isolamento por módulo.
- `AskJobWorker` não herda `BaseWorker` — incompatível com runner genérico e discovery automática.
- `InboxConsumerWorker` silencia `ImportError`/`AttributeError` quando módulo não possui `InboxEventModel` — eventos descartados sem log ou alerta.
- Nenhum worker registry pattern existe; workers são instanciados diretamente no runner com imports concretos.

## Próxima spec recomendada

`023-move-ai-infra-llm-to-agent-infra-llm.md`.

## Pendências de ferramentas

| Ferramenta | Status | Impacto |
|---|---|---|
| rg (ripgrep) | indisponível no ambiente | detecção usa grep tool interno; não bloqueia execução |
| alembic (database) | conexão PostgreSQL indisponível no ambiente local | validações de migração DB registradas como pendência; não bloqueia specs de documentação/testes |
| pytest (full suite) | 10 erros de coleção pré-existentes em test_core e test_identity (faltam __init__.py) | não causados pela migração; não bloqueia spec 000 |
