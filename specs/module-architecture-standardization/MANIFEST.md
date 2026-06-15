# Manifesto das Specs

Branch alvo de execução: `project-rai-playground_module-architecture-standardization`.

Baseline usada no diagnóstico inicial: `project-rai-playground`. A baseline não é branch de implementação.

| Ordem | Spec | Tipo | Dependência principal | Fase |
|---:|---|---|---|---|
| 000 | `000-architecture-decision-record-canonical-module-architecture.md` | architecture | - | decisão e contratos |
| 001 | `001-define-layer-and-module-dependency-rules.md` | architecture | 000 | decisão e contratos |
| 002 | `002-define-canonical-module-directory-contract.md` | architecture | 001 | decisão e contratos |
| 003 | `003-define-module-public-api-and-entrypoints.md` | architecture | 002 | decisão e contratos |
| 004 | `004-define-domain-and-application-contract.md` | architecture | 003 | decisão e contratos |
| 005 | `005-define-infrastructure-database-and-uow-contract.md` | architecture | 004 | decisão e contratos |
| 006 | `006-define-presentation-contract.md` | architecture | 005 | decisão e contratos |
| 007 | `007-define-messaging-and-worker-contract.md` | architecture | 006 | decisão e contratos |
| 008 | `008-define-database-ownership-and-no-cross-module-foreign-keys.md` | database | 007 | decisão e contratos |
| 009 | `009-define-incremental-migration-and-runtime-protocol.md` | architecture | 008 | decisão e contratos |
| 010 | `010-create-module-file-inventory.md` | discovery | 000-009 | discovery |
| 011 | `011-create-current-to-target-structure-matrix.md` | discovery | 000-009 | discovery |
| 012 | `012-create-import-dependency-map.md` | discovery | 000-009 | discovery |
| 013 | `013-create-database-ownership-and-foreign-key-inventory.md` | discovery | 000-009 | discovery |
| 014 | `014-create-route-controller-composer-inventory.md` | discovery | 000-009 | discovery |
| 015 | `015-create-transaction-and-unit-of-work-inventory.md` | discovery | 000-009 | discovery |
| 016 | `016-create-event-outbox-inbox-catalog.md` | discovery | 000-009 | discovery |
| 017 | `017-create-worker-and-registry-inventory.md` | discovery | 000-009 | discovery |
| 018 | `018-create-tests-bootstrap-config-inventory.md` | discovery | 000-009 | discovery |
| 019 | `019-create-standardization-risk-register-and-order.md` | discovery | 000-009 | discovery |
| 020 | `020-audit-agent-as-canonical-reference.md` | refactor | 010-019 | baseline agent |
| 021 | `021-normalize-agent-domain-contracts.md` | refactor | 020 | baseline agent |
| 022 | `022-normalize-agent-application-layout.md` | refactor | 021 | baseline agent |
| 023 | `023-normalize-agent-composers-and-controllers.md` | refactor | 022 | baseline agent |
| 024 | `024-normalize-agent-database-layout.md` | refactor | 023 | baseline agent |
| 025 | `025-make-agent-unit-of-work-the-transaction-boundary.md` | refactor | 024 | baseline agent |
| 026 | `026-normalize-agent-messaging-contracts.md` | refactor | 025 | baseline agent |
| 027 | `027-normalize-agent-workers-and-registry.md` | refactor | 026 | baseline agent |
| 028 | `028-normalize-agent-presentation-contract.md` | refactor | 027 | baseline agent |
| 029 | `029-lock-agent-reference-with-architecture-tests.md` | refactor | 028 | baseline agent |
| 030 | `030-map-current-module-to-canonical-architecture-identity.md` | discovery | 020-029 + inventories | identity |
| 031 | `031-create-canonical-module-skeleton-identity.md` | refactor | 030 | identity |
| 032 | `032-move-and-normalize-domain-layer-identity.md` | refactor | 031 | identity |
| 033 | `033-move-service-to-application-layer-identity.md` | refactor | 032 | identity |
| 034 | `034-normalize-presentation-layer-identity.md` | refactor | 033 | identity |
| 035 | `035-move-infra-to-database-layer-identity.md` | refactor | 034 | identity |
| 036 | `036-implement-module-specific-unit-of-work-identity.md` | refactor | 035 | identity |
| 037 | `037-implement-module-messaging-workers-and-registry-identity.md` | messaging | 036 | identity |
| 038 | `038-add-module-unit-integration-and-contract-tests-identity.md` | test | 037 | identity |
| 039 | `039-remove-legacy-paths-and-temporary-shims-identity.md` | cleanup | 038 | identity |
| 040 | `040-map-current-module-to-canonical-architecture-core.md` | discovery | 020-029 + inventories | core |
| 041 | `041-create-canonical-module-skeleton-core.md` | refactor | 040 | core |
| 042 | `042-move-and-normalize-domain-layer-core.md` | refactor | 041 | core |
| 043 | `043-move-service-to-application-layer-core.md` | refactor | 042 | core |
| 044 | `044-normalize-presentation-layer-core.md` | refactor | 043 | core |
| 045 | `045-move-infra-to-database-layer-core.md` | refactor | 044 | core |
| 046 | `046-implement-module-specific-unit-of-work-core.md` | refactor | 045 | core |
| 047 | `047-implement-module-messaging-workers-and-registry-core.md` | messaging | 046 | core |
| 048 | `048-add-module-unit-integration-and-contract-tests-core.md` | test | 047 | core |
| 049 | `049-remove-legacy-paths-and-temporary-shims-core.md` | cleanup | 048 | core |
| 050 | `050-map-current-module-to-canonical-architecture-billing.md` | discovery | 020-029 + inventories | billing |
| 051 | `051-create-canonical-module-skeleton-billing.md` | refactor | 050 | billing |
| 052 | `052-move-and-normalize-domain-layer-billing.md` | refactor | 051 | billing |
| 053 | `053-move-service-to-application-layer-billing.md` | refactor | 052 | billing |
| 054 | `054-normalize-presentation-layer-billing.md` | refactor | 053 | billing |
| 055 | `055-move-infra-to-database-layer-billing.md` | refactor | 054 | billing |
| 056 | `056-implement-module-specific-unit-of-work-billing.md` | refactor | 055 | billing |
| 057 | `057-implement-module-messaging-workers-and-registry-billing.md` | messaging | 056 | billing |
| 058 | `058-add-module-unit-integration-and-contract-tests-billing.md` | test | 057 | billing |
| 059 | `059-remove-legacy-paths-and-temporary-shims-billing.md` | cleanup | 058 | billing |
| 060 | `060-map-current-module-to-canonical-architecture-metering.md` | discovery | 020-029 + inventories | metering |
| 061 | `061-create-canonical-module-skeleton-metering.md` | refactor | 060 | metering |
| 062 | `062-move-and-normalize-domain-layer-metering.md` | refactor | 061 | metering |
| 063 | `063-move-service-to-application-layer-metering.md` | refactor | 062 | metering |
| 064 | `064-normalize-presentation-layer-metering.md` | refactor | 063 | metering |
| 065 | `065-move-infra-to-database-layer-metering.md` | refactor | 064 | metering |
| 066 | `066-implement-module-specific-unit-of-work-metering.md` | refactor | 065 | metering |
| 067 | `067-implement-module-messaging-workers-and-registry-metering.md` | messaging | 066 | metering |
| 068 | `068-add-module-unit-integration-and-contract-tests-metering.md` | test | 067 | metering |
| 069 | `069-remove-legacy-paths-and-temporary-shims-metering.md` | cleanup | 068 | metering |
| 070 | `070-map-current-module-to-canonical-architecture-observability.md` | discovery | 020-029 + inventories | observability |
| 071 | `071-create-canonical-module-skeleton-observability.md` | refactor | 070 | observability |
| 072 | `072-move-and-normalize-domain-layer-observability.md` | refactor | 071 | observability |
| 073 | `073-move-service-to-application-layer-observability.md` | refactor | 072 | observability |
| 074 | `074-normalize-presentation-layer-observability.md` | refactor | 073 | observability |
| 075 | `075-move-infra-to-database-layer-observability.md` | refactor | 074 | observability |
| 076 | `076-implement-module-specific-unit-of-work-observability.md` | refactor | 075 | observability |
| 077 | `077-implement-module-messaging-workers-and-registry-observability.md` | messaging | 076 | observability |
| 078 | `078-add-module-unit-integration-and-contract-tests-observability.md` | test | 077 | observability |
| 079 | `079-remove-legacy-paths-and-temporary-shims-observability.md` | cleanup | 078 | observability |
| 080 | `080-map-current-module-to-canonical-architecture-tools.md` | discovery | 020-029 + inventories | tools |
| 081 | `081-create-canonical-module-skeleton-tools.md` | refactor | 080 | tools |
| 082 | `082-move-and-normalize-domain-layer-tools.md` | refactor | 081 | tools |
| 083 | `083-move-service-to-application-layer-tools.md` | refactor | 082 | tools |
| 084 | `084-normalize-presentation-layer-tools.md` | refactor | 083 | tools |
| 085 | `085-move-infra-to-database-layer-tools.md` | refactor | 084 | tools |
| 086 | `086-implement-module-specific-unit-of-work-tools.md` | refactor | 085 | tools |
| 087 | `087-implement-module-messaging-workers-and-registry-tools.md` | messaging | 086 | tools |
| 088 | `088-add-module-unit-integration-and-contract-tests-tools.md` | test | 087 | tools |
| 089 | `089-remove-legacy-paths-and-temporary-shims-tools.md` | cleanup | 088 | tools |
| 090 | `090-standardize-versioned-event-envelope.md` | messaging | 030-089 | transversal |
| 091 | `091-standardize-outbox-contract-across-modules.md` | messaging | 090 | transversal |
| 092 | `092-standardize-inbox-contract-across-modules.md` | messaging | 091 | transversal |
| 093 | `093-standardize-rabbitmq-topology.md` | messaging | 092 | transversal |
| 094 | `094-standardize-idempotency-retry-and-dead-letter.md` | messaging | 093 | transversal |
| 095 | `095-wire-central-runner-to-module-worker-registries.md` | worker | 094 | transversal |
| 096 | `096-clean-shared-and-keep-only-technical-contracts.md` | cleanup | 095 | transversal |
| 097 | `097-standardize-bootstrap-dependency-injection-and-config.md` | bootstrap | 096 | transversal |
| 098 | `098-standardize-alembic-expand-migrate-contract.md` | database | 097 | transversal |
| 099 | `099-remove-cross-module-foreign-keys-and-legacy-schema-references.md` | database | 098 | transversal |
| 100 | `100-add-final-layer-dependency-tests.md` | test | 090-099 | validação final |
| 101 | `101-add-final-module-boundary-and-public-api-tests.md` | test | 100 | validação final |
| 102 | `102-add-final-database-ownership-tests.md` | test | 101 | validação final |
| 103 | `103-add-final-uow-transaction-tests.md` | test | 102 | validação final |
| 104 | `104-add-final-messaging-idempotency-and-concurrency-tests.md` | test | 103 | validação final |
| 105 | `105-add-final-api-compatibility-and-openapi-tests.md` | test | 104 | validação final |
| 106 | `106-update-main-bootstrap-migrations-env-and-runtime-entrypoints.md` | bootstrap | 105 | validação final |
| 107 | `107-remove-temporary-allowlists-shims-and-deprecated-paths.md` | cleanup | 106 | validação final |
| 108 | `108-execute-final-architecture-and-behavioral-validation.md` | validation | 107 | validação final |
| 109 | `109-generate-final-standardization-report.md` | report | 108 | validação final |
