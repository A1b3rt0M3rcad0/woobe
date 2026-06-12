# Manifest das Specs

| Ordem | Spec | Tipo | Dependências |
|---:|---|---|---|
| 0 | `000-architecture-decision-record-agent-bounded-context.md` | architecture | - |
| 1 | `001-architecture-rules-modular-monolith-boundaries.md` | architecture | 000 |
| 2 | `002-agent-target-directory-structure.md` | architecture | 000, 001 |
| 3 | `003-create-current-repository-inventory.md` | discovery | 000, 001, 002 |
| 4 | `004-create-current-import-dependency-map.md` | discovery | 000, 001, 002 |
| 5 | `005-create-current-database-ownership-map.md` | discovery | 000, 001, 002 |
| 6 | `006-create-current-api-route-map.md` | discovery | 000, 001, 002 |
| 7 | `007-create-current-event-catalog.md` | discovery | 000, 001, 002 |
| 8 | `008-create-current-worker-inventory.md` | discovery | 000, 001, 002 |
| 9 | `009-create-migration-risk-register.md` | discovery | 000, 001, 002 |
| 10 | `010-create-agent-module-skeleton.md` | refactor | 003, 004, 005, 006, 007, 008, 009 |
| 11 | `011-create-agent-domain-layer-skeleton.md` | refactor | 003, 004, 005, 006, 007, 008, 009 |
| 12 | `012-create-agent-application-layer-skeleton.md` | refactor | 003, 004, 005, 006, 007, 008, 009 |
| 13 | `013-create-agent-infra-layer-skeleton.md` | refactor | 003, 004, 005, 006, 007, 008, 009 |
| 14 | `014-create-agent-presentation-layer-skeleton.md` | refactor | 003, 004, 005, 006, 007, 008, 009 |
| 15 | `015-add-temporary-architecture-boundary-tests.md` | test | 000, 001, 002, 003, 004, 008 |
| 16 | `016-add-shared-layer-architecture-tests.md` | test | 000, 001, 002, 003, 004, 008 |
| 17 | `017-add-worker-location-architecture-tests.md` | test | 000, 001, 002, 003, 004, 008 |
| 18 | `018-add-agent-boundary-architecture-tests.md` | test | 000, 001, 002, 003, 004, 008 |
| 19 | `019-add-legacy-module-allowlist.md` | test | 000, 001, 002, 003, 004, 008 |
| 20 | `020-map-ai-to-agent.md` | migration | 003, 004, 005, 006, 007, 008, 009, 015, 016, 017, 018, 019 |
| 21 | `021-move-ai-domain-to-agent-domain.md` | migration | 010, 011, 012, 013, 014, 015, 016, 017, 018, 019, 020 |
| 22 | `022-move-ai-application-to-agent-application.md` | migration | 010, 011, 012, 013, 014, 015, 016, 017, 018, 019, 020 |
| 23 | `023-move-ai-infra-llm-to-agent-infra-llm.md` | migration | 010, 011, 012, 013, 014, 015, 016, 017, 018, 019, 020 |
| 24 | `024-move-ai-presentation-to-agent-presentation.md` | migration | 010, 011, 012, 013, 014, 015, 016, 017, 018, 019, 020 |
| 25 | `025-update-ai-imports-to-agent-imports.md` | migration | 010, 011, 012, 013, 014, 015, 016, 017, 018, 019, 020 |
| 30 | `030-map-knowledge-to-agent.md` | migration | 003, 004, 005, 006, 007, 008, 009, 015, 016, 017, 018, 019 |
| 31 | `031-move-knowledge-domain-to-agent-domain.md` | migration | 025, 030 |
| 32 | `032-move-knowledge-application-to-agent-application.md` | migration | 025, 030 |
| 33 | `033-move-knowledge-infra-to-agent-infra.md` | migration | 025, 030 |
| 34 | `034-move-knowledge-presentation-to-agent-presentation.md` | migration | 025, 030 |
| 35 | `035-update-knowledge-imports-to-agent-imports.md` | migration | 025, 030 |
| 40 | `040-map-runtime-to-agent.md` | migration | 003, 004, 005, 006, 007, 008, 009, 015, 016, 017, 018, 019 |
| 41 | `041-move-runtime-domain-to-agent-domain.md` | migration | 035, 040 |
| 42 | `042-move-runtime-application-to-agent-application.md` | migration | 035, 040 |
| 43 | `043-move-runtime-infra-to-agent-infra.md` | migration | 035, 040 |
| 44 | `044-move-runtime-presentation-to-agent-presentation.md` | migration | 035, 040 |
| 45 | `045-update-runtime-imports-to-agent-imports.md` | migration | 035, 040 |
| 50 | `050-create-shared-worker-contracts.md` | worker | 015, 016, 017, 018, 019 |
| 51 | `051-create-shared-outbox-dispatcher-base.md` | worker | 015, 016, 017, 018, 019 |
| 52 | `052-create-shared-inbox-consumer-base.md` | worker | 015, 016, 017, 018, 019 |
| 53 | `053-create-shared-inbox-processor-base.md` | worker | 015, 016, 017, 018, 019 |
| 54 | `054-create-shared-worker-runner.md` | worker | 015, 016, 017, 018, 019 |
| 55 | `055-create-shared-worker-registry-contract.md` | worker | 015, 016, 017, 018, 019 |
| 60 | `060-move-root-workers-to-shared-workers.md` | worker | 050, 051, 052, 053, 054, 055 |
| 61 | `061-remove-domain-worker-implementation-from-src-workers.md` | cleanup | 050, 051, 052, 053, 054, 055 |
| 62 | `062-create-module-worker-registry-pattern.md` | worker | 050, 051, 052, 053, 054, 055 |
| 63 | `063-wire-central-runner-to-module-worker-registries.md` | bootstrap | 050, 051, 052, 053, 054, 055 |
| 70 | `070-create-agent-outbox-model-and-repository.md` | database | 010, 011, 012, 013, 014, 045 |
| 71 | `071-create-agent-inbox-model-and-repository.md` | database | 010, 011, 012, 013, 014, 045 |
| 72 | `072-create-agent-event-contracts.md` | messaging | 010, 011, 012, 013, 014, 045 |
| 73 | `073-create-agent-event-mappers.md` | messaging | 010, 011, 012, 013, 014, 045 |
| 74 | `074-create-agent-unit-of-work.md` | database | 010, 011, 012, 013, 014, 045 |
| 75 | `075-create-agent-outbox-database-migration.md` | database | 010, 011, 012, 013, 014, 045 |
| 76 | `076-create-agent-inbox-database-migration.md` | database | 010, 011, 012, 013, 014, 045 |
| 77 | `077-create-agent-outbox-status-transition-policy.md` | database | 010, 011, 012, 013, 014, 045 |
| 78 | `078-create-agent-inbox-status-transition-policy.md` | database | 010, 011, 012, 013, 014, 045 |
| 79 | `079-create-agent-outbox-inbox-locking-policy.md` | database | 010, 011, 012, 013, 014, 045 |
| 80 | `080-implement-agent-outbox-dispatcher.md` | worker | 050, 051, 052, 053, 054, 055, 070, 071, 072, 073, 074, 075, 076, 077, 078, 079 |
| 81 | `081-implement-agent-rabbitmq-publisher.md` | worker | 050, 051, 052, 053, 054, 055, 070, 071, 072, 073, 074, 075, 076, 077, 078, 079 |
| 82 | `082-implement-agent-inbox-consumer.md` | worker | 050, 051, 052, 053, 054, 055, 070, 071, 072, 073, 074, 075, 076, 077, 078, 079 |
| 83 | `083-implement-agent-inbox-processor.md` | worker | 050, 051, 052, 053, 054, 055, 070, 071, 072, 073, 074, 075, 076, 077, 078, 079 |
| 84 | `084-implement-agent-inbox-handlers.md` | worker | 050, 051, 052, 053, 054, 055, 070, 071, 072, 073, 074, 075, 076, 077, 078, 079 |
| 85 | `085-implement-agent-worker-registry.md` | worker | 050, 051, 052, 053, 054, 055, 070, 071, 072, 073, 074, 075, 076, 077, 078, 079 |
| 90 | `090-create-billing-worker-structure.md` | worker | 050, 051, 052, 053, 054, 055, 062, 063 |
| 91 | `091-create-metering-worker-structure.md` | worker | 050, 051, 052, 053, 054, 055, 062, 063 |
| 92 | `092-create-identity-worker-structure.md` | worker | 050, 051, 052, 053, 054, 055, 062, 063 |
| 93 | `093-create-tools-worker-structure.md` | worker | 050, 051, 052, 053, 054, 055, 062, 063 |
| 94 | `094-create-observability-worker-structure.md` | worker | 050, 051, 052, 053, 054, 055, 062, 063 |
| 100 | `100-standardize-module-outbox-pattern.md` | messaging | 070, 071, 072, 073, 074, 080, 081, 082, 083, 084, 085 |
| 101 | `101-standardize-module-inbox-pattern.md` | messaging | 070, 071, 072, 073, 074, 080, 081, 082, 083, 084, 085 |
| 102 | `102-standardize-event-envelope.md` | messaging | 070, 071, 072, 073, 074, 080, 081, 082, 083, 084, 085 |
| 103 | `103-standardize-event-idempotency.md` | messaging | 070, 071, 072, 073, 074, 080, 081, 082, 083, 084, 085 |
| 104 | `104-standardize-event-retry-policy.md` | messaging | 070, 071, 072, 073, 074, 080, 081, 082, 083, 084, 085 |
| 105 | `105-standardize-dead-letter-policy.md` | messaging | 070, 071, 072, 073, 074, 080, 081, 082, 083, 084, 085 |
| 106 | `106-standardize-rabbitmq-topology.md` | messaging | 070, 071, 072, 073, 074, 080, 081, 082, 083, 084, 085 |
| 107 | `107-standardize-event-versioning-policy.md` | messaging | 070, 071, 072, 073, 074, 080, 081, 082, 083, 084, 085 |
| 108 | `108-standardize-event-observability-and-tracing.md` | messaging | 070, 071, 072, 073, 074, 080, 081, 082, 083, 084, 085 |
| 109 | `109-standardize-event-compatibility-policy.md` | messaging | 070, 071, 072, 073, 074, 080, 081, 082, 083, 084, 085 |
| 110 | `110-update-import-boundary-rules.md` | test | 100, 101, 102, 103, 104, 105, 106, 107, 108, 109 |
| 111 | `111-add-architecture-tests-for-module-boundaries.md` | test | 100, 101, 102, 103, 104, 105, 106, 107, 108, 109 |
| 112 | `112-add-architecture-tests-for-shared-layer.md` | test | 100, 101, 102, 103, 104, 105, 106, 107, 108, 109 |
| 113 | `113-add-architecture-tests-for-workers.md` | test | 100, 101, 102, 103, 104, 105, 106, 107, 108, 109 |
| 114 | `114-add-architecture-tests-for-agent-module.md` | test | 100, 101, 102, 103, 104, 105, 106, 107, 108, 109 |
| 120 | `120-add-agent-unit-tests.md` | test | 070, 071, 072, 073, 074, 075, 076, 077, 078, 079, 080, 081, 082, 083, 084, 085 |
| 121 | `121-add-agent-integration-tests.md` | test | 070, 071, 072, 073, 074, 075, 076, 077, 078, 079, 080, 081, 082, 083, 084, 085 |
| 122 | `122-add-outbox-dispatcher-tests.md` | test | 070, 071, 072, 073, 074, 075, 076, 077, 078, 079, 080, 081, 082, 083, 084, 085 |
| 123 | `123-add-inbox-consumer-tests.md` | test | 070, 071, 072, 073, 074, 075, 076, 077, 078, 079, 080, 081, 082, 083, 084, 085 |
| 124 | `124-add-inbox-processor-tests.md` | test | 070, 071, 072, 073, 074, 075, 076, 077, 078, 079, 080, 081, 082, 083, 084, 085 |
| 125 | `125-add-idempotency-tests.md` | test | 070, 071, 072, 073, 074, 075, 076, 077, 078, 079, 080, 081, 082, 083, 084, 085 |
| 126 | `126-add-unit-of-work-transaction-tests.md` | test | 070, 071, 072, 073, 074, 075, 076, 077, 078, 079, 080, 081, 082, 083, 084, 085 |
| 127 | `127-add-rabbitmq-publisher-confirm-tests.md` | test | 070, 071, 072, 073, 074, 075, 076, 077, 078, 079, 080, 081, 082, 083, 084, 085 |
| 128 | `128-add-inbox-deduplication-concurrency-tests.md` | test | 070, 071, 072, 073, 074, 075, 076, 077, 078, 079, 080, 081, 082, 083, 084, 085 |
| 129 | `129-add-outbox-dispatch-concurrency-tests.md` | test | 070, 071, 072, 073, 074, 075, 076, 077, 078, 079, 080, 081, 082, 083, 084, 085 |
| 130 | `130-update-application-bootstrap.md` | bootstrap | 045, 063, 085, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109 |
| 131 | `131-update-api-routes-to-agent.md` | bootstrap | 045, 063, 085, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109 |
| 132 | `132-update-dependency-injection-bindings.md` | bootstrap | 045, 063, 085, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109 |
| 133 | `133-update-settings-and-config.md` | bootstrap | 045, 063, 085, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109 |
| 134 | `134-update-alembic-or-database-migrations.md` | database | 045, 063, 085, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109 |
| 140 | `140-deprecate-ai-module.md` | cleanup | 130, 131, 132, 133, 134, 110, 111, 112, 113, 114 |
| 141 | `141-deprecate-knowledge-module.md` | cleanup | 130, 131, 132, 133, 134, 110, 111, 112, 113, 114 |
| 142 | `142-deprecate-runtime-module.md` | cleanup | 130, 131, 132, 133, 134, 110, 111, 112, 113, 114 |
| 143 | `143-remove-legacy-ai-module.md` | cleanup | 140, 141, 142, 110, 111, 112, 113, 114, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134 |
| 144 | `144-remove-legacy-knowledge-module.md` | cleanup | 140, 141, 142, 150 |
| 145 | `145-remove-legacy-runtime-module.md` | cleanup | 140, 141, 142, 150 |
| 150 | `150-final-cleanup-imports.md` | cleanup | 143, 144, 145 |
| 151 | `151-final-cleanup-dead-code.md` | cleanup | 143, 144, 145 |
| 152 | `152-final-cleanup-src-workers.md` | cleanup | 143, 144, 145 |
| 153 | `153-final-architecture-validation.md` | validation | 150, 151, 152, 110, 111, 112, 113, 114, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129 |
| 154 | `154-final-migration-report.md` | report | 153 |
