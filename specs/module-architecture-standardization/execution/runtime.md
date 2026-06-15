# Runtime da Padronização Arquitetural dos Módulos

## Objetivo da migração

Padronizar `identity`, `core`, `billing`, `metering`, `observability` e `tools` na arquitetura em camadas adotada por `modules.agent`, preservando cada bounded context e migrando incrementalmente a branch `project-rai-playground_module-architecture-standardization`.

## Branch de execução

`project-rai-playground_module-architecture-standardization`. Esta é a única branch autorizada para implementar as specs. Toda execução deve registrar o SHA inicial, verificar se a branch avançou desde o último inventário e falhar imediatamente quando `git branch --show-current` retornar outro nome.

## Baseline de origem

`project-rai-playground` foi usada apenas para o diagnóstico inicial. Alterações de implementação não devem ser aplicadas diretamente nela.

## Estado obrigatório da branch

```yaml
expected_branch: project-rai-playground_module-architecture-standardization
source_baseline: project-rai-playground
initial_sha: c128cb06372ecd0d748a144a91093ca3417a590c
last_validated_sha: 369546b8ff3c87c9c1a4ce940f91ea4aebcacece
branch_guard_status: active
```

Comando obrigatório antes de qualquer spec:

```bash
test "$(git branch --show-current)" = "project-rai-playground_module-architecture-standardization"
git rev-parse HEAD
```

## Decisão arquitetural principal

Todos os módulos de domínio usam o mesmo contrato estrutural e a mesma direção de dependências. Padronização não significa compartilhar domínio nem fundir bounded contexts.

## Estrutura canônica

```text
src/modules/<module>/
├── application
│   ├── composers
│   ├── dtos
│   ├── handlers
│   └── use_cases
├── domain
│   ├── entities.py
│   ├── enums.py
│   ├── errors.py
│   ├── events.py
│   ├── repositories.py
│   ├── services.py
│   └── value_objects.py
├── infra
│   ├── database
│   │   ├── mappers.py
│   │   ├── models.py
│   │   ├── repositories.py
│   │   └── unit_of_work.py
│   ├── messaging
│   │   ├── consumers.py
│   │   ├── event_mappers.py
│   │   └── publishers.py
│   └── workers
│       ├── inbox_consumer.py
│       ├── inbox_processor.py
│       ├── outbox_dispatcher.py
│       └── registry.py
└── presentation
    ├── controllers
    ├── mappers.py
    ├── routes.py
    └── schemas.py
```

## Regras absolutas

- domínio não importa application, infra ou presentation;
- application importa apenas domínio próprio e contratos técnicos mínimos de `shared`;
- presentation delega para application e não acessa repositories/models;
- infra implementa ports do domínio/application e não contém regra de negócio;
- módulos não importam internals de outros módulos;
- alteração de estado entre módulos ocorre somente por Outbox/RabbitMQ/Inbox;
- Foreign Key física cross-module é proibida no estado final;
- IDs externos podem ser armazenados como UUIDs opacos, sem constraint para tabela de outro módulo;
- UoW coordena apenas repositories, Inbox e Outbox do próprio módulo;
- workers concretos pertencem ao módulo e apenas delegam para handlers/use cases;
- `shared` contém somente infraestrutura e contratos técnicos reutilizáveis.

## Baseline observado

- `agent` já possui diretórios `application`, `domain`, `infra/database`, `infra/messaging`, `infra/workers` e `presentation`;
- `AgentUnitOfWork` expõe repositories próprios, Inbox e Outbox, mas composers ainda podem instanciar `PostgresUnitOfWork` genérico;
- módulos restantes mantêm `service/` e `infra/models.py`/`infra/repositories.py` planos;
- há FKs cross-module em `core`, `billing`, `metering`, `observability` e `tools`;
- há referências legadas a schemas removidos/renomeados (`ai` e `runtime`) em módulos consumidores;
- nomes de eventos não estão uniformemente namespaced/versionados.

## Ordem recomendada

1. discovery e testes de arquitetura com allowlist;
2. estabilização do contrato do `agent`;
3. `identity`;
4. `core`;
5. `billing`;
6. `metering`;
7. `observability`;
8. `tools`;
9. padrões transversais, banco, bootstrap e limpeza final.

## Fora de escopo

- microservices;
- fusão dos bounded contexts restantes;
- reescrita funcional de regras de negócio;
- mudança não versionada de contratos HTTP;
- troca de FastAPI, SQLAlchemy, Alembic ou RabbitMQ;
- criação de abstrações genéricas sem pelo menos dois consumidores reais.

## Estado atual da migração

`in_progress`

## Status das specs

| Spec | Status | Data | Arquivos alterados | Pendências | Próxima recomendada |
|---|---|---|---|---|---|
| 000 | completed | 2026-06-14 | `specs/module-architecture-standardization/000-architecture-decision-record-canonical-module-architecture.md`, `tests/architecture/test_adr_presence.py`, `execution/runtime.md` | ruff F821/F401/F841 pré-existentes (não introduzidos pela spec) | 001 |
| 001 | completed | 2026-06-14 | `specs/module-architecture-standardization/001-layer-dependency-rules.md`, `tests/architecture/test_layer_dependencies.py`, `tests/architecture/legacy_import_allowlist.yaml`, `execution/runtime.md` | ruff F821/F401/F841 pré-existentes (não introduzidos pela spec); layer_dependencies: agent use_cases e tools/service/use_cases allowlistados | 002 |
| 002 | completed | 2026-06-14 | `specs/module-architecture-standardization/002-define-canonical-module-directory-contract.md`, `tests/architecture/test_module_structure.py`, `execution/runtime.md` | ruff F821/F401/F841 pré-existentes (não introduzidos pela spec); domain/services.py, events.py, value_objects.py condicionais (não obrigatórios) | 003 |
| 003 | completed | 2026-06-14 | `src/modules/*/__init__.py` (7 modules), `tests/architecture/test_public_module_entrypoints.py`, `execution/runtime.md` | ruff F821/F401/F841 pré-existentes (não introduzidos pela spec) | 004 |
| 004 | completed | 2026-06-14 | `tests/architecture/test_application_boundaries.py`, `tests/architecture/legacy_import_allowlist.yaml`, `execution/runtime.md` | ruff F821/F401/F841 pré-existentes (não introduzidos pela spec); agent/tools use_cases allowlistados por importarem sqlalchemy | 005 |
| 005 | completed | 2026-06-14 | `tests/architecture/test_uow_ownership.py`, `tests/integration/test_module_uow_transactions.py`, `tests/architecture/legacy_import_allowlist.yaml`, `execution/runtime.md` | ruff F821/F401/F841 pré-existentes; PostgresUnitOfWork em todos os composers (allowlistado em uow_ownership scope, removal_spec 025-036); `rg` indisponível (substituído por grep) | 006 |
| 006 | completed | 2026-06-14 | `tests/contract/__init__.py`, `tests/contract/test_http_routes_compatibility.py`, `execution/runtime.md` | mappers.py condicional (5 módulos sem mappers ainda); `rg` indisponível (substituído por grep) | 007 |
| 007 | completed | 2026-06-14 | `tests/integration/test_outbox_inbox_flow.py`, `execution/runtime.md` | `test_worker_locations.py` pré-existente inalterado (4 testes válidos); `rg` indisponível (substituído por grep) | 008 |
| 008 | completed | 2026-06-14 | `tests/architecture/test_no_cross_module_foreign_keys.py`, `specs/module-architecture-standardization/execution/inventory/database-ownership.md`, `execution/runtime.md` | 32 critical legacy schema refs (ai/knowledge/runtime) catalogued; `rg` indisponível (substituído por grep) | 009 |
| 009 | completed | 2026-06-14 | `tests/architecture/test_runtime_manifest_consistency.py`, `execution/runtime.md` | `rg` indisponível (substituído por grep); pyright com 482 erros pré-existentes não relacionados | 010 |
| 010 | completed | 2026-06-14 | `specs/module-architecture-standardization/execution/inventory/files.md`, `tests/architecture/test_inventory_artifacts.py`, `execution/runtime.md` | `find` Unix tool unavailable (substituted with Get-ChildItem); `rg` unavailable (not used in this spec) | 011 |
| 011 | completed | 2026-06-14 | `specs/module-architecture-standardization/execution/inventory/structure-matrix.md`, `execution/runtime.md` | `find` Unix tool unavailable (substituted with Get-ChildItem) | 012 |
| 012 | completed | 2026-06-14 | `specs/module-architecture-standardization/execution/inventory/imports.md`, `execution/runtime.md` | `rg` unavailable (substituted with Select-String); `scripts/architecture/import_graph.py` not found | 013 |
| 013 | completed | 2026-06-14 | `specs/module-architecture-standardization/execution/inventory/database-ownership.md`, `execution/runtime.md` | `rg` unavailable (substituted with Select-String); inventory already populated by spec 008, extended with migration schema section | 014 |
| 014 | completed | 2026-06-14 | `specs/module-architecture-standardization/execution/inventory/routes.md`, `execution/runtime.md` | `rg` unavailable (substituted with Select-String); agent has 4 routers including legacy /ai, /knowledge, /runtime prefixes | 015 |
| 015 | completed | 2026-06-14 | `specs/module-architecture-standardization/execution/inventory/transactions.md`, `tests/architecture/test_inventory_artifacts.py`, `execution/runtime.md` | `rg` unavailable (substituted with Select-String); 89 composers using PostgresUnitOfWork (generic); 6 modules without module-specific UoW | 016 |
| 016 | completed | 2026-06-14 | `specs/module-architecture-standardization/execution/inventory/events.md`, `tests/architecture/test_inventory_artifacts.py`, `execution/runtime.md` | `rg` unavailable (substituted with Select-String); only agent uses versioned events; 6 modules use unversioned event_type strings; agent has 3 separate outbox/inbox writer pairs | 017 |
| 017 | completed | 2026-06-14 | `specs/module-architecture-standardization/execution/inventory/workers.md`, `tests/architecture/test_inventory_artifacts.py`, `execution/runtime.md` | `find`/`rg` unavailable (substituted with Get-ChildItem/Select-String); core has no workers dir; 5 modules have empty registry stubs; AskJobWorker has cross-module import | 018 |
| 018 | completed | 2026-06-14 | `specs/module-architecture-standardization/execution/inventory/tests-bootstrap.md`, `tests/architecture/test_inventory_artifacts.py`, `execution/runtime.md` | `find`/`sed` unavailable (substituted with Get-ChildItem/Get-Content); e2e dir empty; core unit tests missing __init__.py; 34 pre-existing arch test failures | 019 |
| 019 | completed | 2026-06-14 | `specs/module-architecture-standardization/execution/inventory/risks.md`, `tests/architecture/test_inventory_artifacts.py`, `execution/runtime.md` | 25 riscos catalogados (5 críticos, 12 altos, 6 médios, 2 baixos); `rg`/`find`/`cat` indisponíveis (substituídos) | 020 |
| 020 | completed | 2026-06-14 | `tests/modules/agent/test_audit_agent_as_canonical_reference.py`, `tests/architecture/test_agent_reference_architecture.py`, `execution/runtime.md` | ruff limpo; 0 legacy ai/knowledge/runtime imports; 8 auditoria + 11 testes de arquitetura criados; pyright com 482 erros pré-existentes (não introduzidos) | 021 |
| 021 | completed | 2026-06-14 | `tests/modules/agent/test_normalize_agent_domain_contracts.py`, `tests/architecture/test_agent_reference_architecture.py`, `execution/runtime.md` | 13 testes de contratos de domínio + 2 testes de arquitetura adicionados; domain services.py e value_objects.py são stubs (sem lógica de negócio a adicionar); ruff limpo | 022 |
| 022 | completed | 2026-06-14 | `tests/modules/agent/test_normalize_agent_application_layout.py`, `tests/architecture/test_agent_reference_architecture.py`, `src/modules/agent/application/dtos/__init__.py`, `src/modules/agent/application/use_cases/__init__.py`, `src/modules/agent/presentation/mappers.py`, `execution/runtime.md` | dtos e use_cases packages com __all__ exports (~70 DTOs, ~46 use cases); mappers.py migrado para importar de dtos (não dtos.knowledge_dtos); 2 testes de arquitetura + 8 testes de layout adicionados; ask_agent_stream_service e ask_use_case allowlistados por imports de infra/llm pré-existentes | 023 |
| 023 | pending | - | - | - | 024 |
| 024 | pending | - | - | - | 025 |
| 025 | pending | - | - | - | 026 |
| 026 | pending | - | - | - | 027 |
| 027 | pending | - | - | - | 028 |
| 028 | pending | - | - | - | 029 |
| 029 | pending | - | - | - | 030 |
| 030 | pending | - | - | - | 031 |
| 031 | pending | - | - | - | 032 |
| 032 | pending | - | - | - | 033 |
| 033 | pending | - | - | - | 034 |
| 034 | pending | - | - | - | 035 |
| 035 | pending | - | - | - | 036 |
| 036 | pending | - | - | - | 037 |
| 037 | pending | - | - | - | 038 |
| 038 | pending | - | - | - | 039 |
| 039 | pending | - | - | - | 040 |
| 040 | pending | - | - | - | 041 |
| 041 | pending | - | - | - | 042 |
| 042 | pending | - | - | - | 043 |
| 043 | pending | - | - | - | 044 |
| 044 | pending | - | - | - | 045 |
| 045 | pending | - | - | - | 046 |
| 046 | pending | - | - | - | 047 |
| 047 | pending | - | - | - | 048 |
| 048 | pending | - | - | - | 049 |
| 049 | pending | - | - | - | 050 |
| 050 | pending | - | - | - | 051 |
| 051 | pending | - | - | - | 052 |
| 052 | pending | - | - | - | 053 |
| 053 | pending | - | - | - | 054 |
| 054 | pending | - | - | - | 055 |
| 055 | pending | - | - | - | 056 |
| 056 | pending | - | - | - | 057 |
| 057 | pending | - | - | - | 058 |
| 058 | pending | - | - | - | 059 |
| 059 | pending | - | - | - | 060 |
| 060 | pending | - | - | - | 061 |
| 061 | pending | - | - | - | 062 |
| 062 | pending | - | - | - | 063 |
| 063 | pending | - | - | - | 064 |
| 064 | pending | - | - | - | 065 |
| 065 | pending | - | - | - | 066 |
| 066 | pending | - | - | - | 067 |
| 067 | pending | - | - | - | 068 |
| 068 | pending | - | - | - | 069 |
| 069 | pending | - | - | - | 070 |
| 070 | pending | - | - | - | 071 |
| 071 | pending | - | - | - | 072 |
| 072 | pending | - | - | - | 073 |
| 073 | pending | - | - | - | 074 |
| 074 | pending | - | - | - | 075 |
| 075 | pending | - | - | - | 076 |
| 076 | pending | - | - | - | 077 |
| 077 | pending | - | - | - | 078 |
| 078 | pending | - | - | - | 079 |
| 079 | pending | - | - | - | 080 |
| 080 | pending | - | - | - | 081 |
| 081 | pending | - | - | - | 082 |
| 082 | pending | - | - | - | 083 |
| 083 | pending | - | - | - | 084 |
| 084 | pending | - | - | - | 085 |
| 085 | pending | - | - | - | 086 |
| 086 | pending | - | - | - | 087 |
| 087 | pending | - | - | - | 088 |
| 088 | pending | - | - | - | 089 |
| 089 | pending | - | - | - | 090 |
| 090 | pending | - | - | - | 091 |
| 091 | pending | - | - | - | 092 |
| 092 | pending | - | - | - | 093 |
| 093 | pending | - | - | - | 094 |
| 094 | pending | - | - | - | 095 |
| 095 | pending | - | - | - | 096 |
| 096 | pending | - | - | - | 097 |
| 097 | pending | - | - | - | 098 |
| 098 | pending | - | - | - | 099 |
| 099 | pending | - | - | - | 100 |
| 100 | pending | - | - | - | 101 |
| 101 | pending | - | - | - | 102 |
| 102 | pending | - | - | - | 103 |
| 103 | pending | - | - | - | 104 |
| 104 | pending | - | - | - | 105 |
| 105 | pending | - | - | - | 106 |
| 106 | pending | - | - | - | 107 |
| 107 | pending | - | - | - | 108 |
| 108 | pending | - | - | - | 109 |
| 109 | pending | - | - | - | - |

## Specs executadas

| Spec | Data | SHA | Resumo |
|---|---|---|---|
| 000 | 2026-06-14 | c128cb0 | ADR canônico registrado: agente como referência, 6 módulos-alvo, proibição FK/imports cross-module. Teste arquitetural criado e validado. |
| 001 | 2026-06-14 | 8b01eb4 | Regras de dependência por camada e módulo documentadas. Teste `test_layer_dependencies.py` criado com AST scan e allowlist. `test_module_boundaries.py` verificado (4/4 pass). Allowlist com scope `layer_dependencies` para 3 violações legadas (use_cases → infra). |
| 002 | 2026-06-14 | ff62fa0 | Estrutura canônica documentada e testada. `test_module_structure.py` com 4 testes: estrutura geral, service/ legado, agent infra canônica, infra plana dos demais módulos. Domain files obrigatórios e condicionais distinguidos. |
| 003 | 2026-06-14 | 14eddd1 | `__init__.py` de todos os 7 módulos expõem `routes` e `registry` via `__all__`. `test_public_module_entrypoints.py` com 5 testes: routes exportadas, registry exportado, __all__ definido, rotas importáveis, registries importáveis. |
| 004 | 2026-06-14 | 639a77c | Contratos domain/application definidos. `test_application_boundaries.py` com 3 testes: nenhum use case importa FastAPI/SQLAlchemy (2 allowlistados), composer sem lógica de domínio, DTOs fora de shared. |
| 005 | 2026-06-14 | acc92b6 | Contrato infra/database/UoW definido. `test_uow_ownership.py` com 3 testes: UoW sem imports cross-module, PostgresUnitOfWork allowlistado em composers, agent UoW expõe outbox/inbox. `test_module_uow_transactions.py` com 4 testes de contrato de transação. Allowlist scope `uow_ownership` para todos os composers com PostgresUnitOfWork. |
| 006 | 2026-06-14 | ea56b9c | Contrato presentation definido. `test_http_routes_compatibility.py` com 5 testes: estrutura obrigatória, routes sem infra/domain, controllers sem sessão SQLAlchemy, mappers condicionais. |
| 007 | 2026-06-14 | e7dab1a | Contrato messaging/worker definido. `test_outbox_inbox_flow.py` com 5 testes de contrato (consumer antes ack, processor idempotente, dispatcher pós-commit, claim/process, dead letter). `test_worker_locations.py` pré-existente confirmado. |
| 008 | 2026-06-14 | ababd34 | Database ownership inventory. `test_no_cross_module_foreign_keys.py` com 3 testes: classificação intra/cross, legacy schemas críticos, migrations. `database-ownership.md` inventário com ~33 cross-module FKs e 32 legacy refs. |
| 009 | 2026-06-14 | ababd34 | Runtime protocol definido. `test_runtime_manifest_consistency.py` com 6 testes: runtime.md existente, todas as specs 000-109, próxima recomendada, allowlist fields, manifest completo, spec ordering. |
| 010 | 2026-06-14 | 763ef71 | File inventory criado: `files.md` com listing completo dos 7 módulos (284 source files), gaps vs canonical structure identificados. `test_inventory_artifacts.py` criado com 9 testes. |
| 011 | 2026-06-14 | d6ee29c | Current-to-target structure matrix criado: `structure-matrix.md` com mapeamento completo por módulo (keep/move/create), gaps catalogados. |
| 012 | 2026-06-14 | 8ffa987 | Import dependency map criado: `imports.md` com classificação cross/intra-module, legacy refs catalogadas, service layer gap identificado. |
| 013 | 2026-06-14 | a622072 | Database ownership inventory atualizado: `database-ownership.md` verificado e estendido com migration schema section; ~69 FKs catalogadas (33 cross-module, 18 legacy, ~16 intra). |
| 014 | 2026-06-14 | a622072 | Route-controller-composer inventory criado: `routes.md` com mapeamento rota→composer→controller para 7 módulos; agent tem 4 routers (/ai, /knowledge, /runtime, /agent), demais têm 1 cada. |
| 015 | 2026-06-14 | 369546b | Transaction/UoW inventory criado: `transactions.md` com 3 UoW classes catalogadas, 89 compositores usando PostgresUnitOfWork, commit/rollback call sites, gaps e riscos. `rg` indisponível (Select-String). |
| 016 | 2026-06-14 | d12e2b6 | Event/Outbox/Inbox catalog criado: `events.md` com 19 event_types catalogados, agent com eventos versionados (5 tipos), demais módulos sem versionamento, 3 OutboxEventWriter no agent, 6 módulos com outbox/inbox models. |
| 017 | 2026-06-14 | bd9aa35 | Worker/registry inventory criado: `workers.md` com 26 arquivos catalogados; agent tem 4 workers concretos + registry; billing/identity/metering/observability/tools têm registries vazios; core sem workers dir; AskJobWorker com import cross-module. |
| 018 | 2026-06-14 | 54ab80e | Tests/bootstrap/config inventory criado: `tests-bootstrap.md` com 150 test files catalogados, bootstrap (main.py), Alembic (15 migrações), pyproject.toml; e2e dir vazio; wildcard imports em env.py. |
| 019 | 2026-06-14 | 1e87c8e | Risk register and execution order criado: `risks.md` com 25 riscos consolidados dos 10 inventários (010-018); ordem executável em 9 fases; 5 riscos críticos (FKs cross-module, schemas legados), 12 altos, 6 médios, 2 baixos. |
| 020 | 2026-06-14 | 16126be | Auditoria do agent como referência canônica concluída: 137 arquivos Python analisados, 0 imports legados `ai`/`knowledge`/`runtime`, 90 ocorrências PostgresUnitOfWork catalogadas (44 composers + 1 worker), AgentUnitOfWork coordena apenas repositórios do agent + outbox + inbox. 2 conjuntos de testes criados (19 testes). Agent confirmado como baseline canônica para os demais módulos. |
| 021 | 2026-06-14 | 8e5152c | Normalização dos contratos de domínio do agent concluída: entities, enums, errors, events, repositories validados; services.py e value_objects.py são stubs (1 linha cada). 13 testes de contratos de domínio + 2 testes de arquitetura adicionados. |
| 022 | 2026-06-14 | 3200f2c | Layout da application layer normalizado: dtos/__init__.py e use_cases/__init__.py com re-exports completos (~70 DTOs, ~46 use cases); mappers.py importa de dtos (não dtos.knowledge_dtos); 10 testes de layout + 3 testes de arquitetura adicionados; 2 use cases com imports de infra allowlistados (pré-existentes). |

## Specs pendentes

Specs 015 a 109 do `MANIFEST.md`.

## Decisões tomadas durante a execução

| Data | Decisão | Motivo | Impacto | Reversível? |
|---|---|---|---|---|
| 2026-06-14 | ADR canônico registrado e aceito | Estabelecer base arquitetural obrigatória antes de qualquer migração física | Todos os módulos devem seguir o mesmo contrato estrutural; proibição de FK e imports cross-module | Sim, revertendo o ADR e runtime.md |
| 2026-06-14 | Regras de dependência por camada definidas | Especificar imports permitidos/proibidos por camada antes de mover arquivos | Layer test + AST scan + allowlist com scope layer_dependencies; composers exempt por serem raiz de DI | Sim, removendo regras e allowlist |
| 2026-06-14 | Estrutura canônica de diretórios definida | Padronizar responsabilidades sem criar abstrações vazias | `test_module_structure.py` com 4 testes; domain files obrigatórios vs condicionais; agent infra canônica vs outros com infra plana | Sim, revertendo teste e doc |
| 2026-06-14 | API pública dos módulos definida via __init__.py | Bootstrap, workers e rotas acessam módulos sem importar internals | Todos os 7 módulos expõem routes e registry via __all__; 5 testes de entrypoint | Sim, revertendo __init__.py e teste |
| 2026-06-14 | Contratos domain/application definidos | Use cases não importam FastAPI/SQLAlchemy; composers sem lógica de domínio; DTOs fora de shared | `test_application_boundaries.py` com 3 testes; 2 allowlist entries para sqlalchemy em use_cases | Sim, revertendo teste e allowlist |
| 2026-06-14 | Contrato infra/database/UoW definido | Estabelecer que cada módulo tem UoW concreto que coordena apenas seus repositories, outbox e inbox | `test_uow_ownership.py` com 3 testes; allowlist uow_ownership para PostgresUnitOfWork em todos os composers; `test_module_uow_transactions.py` com 4 testes de contrato | Sim, revertendo testes e runtime.md |
| 2026-06-14 | Contrato presentation definido | Padronizar controllers, routes, schemas e mappers sem alterar contratos HTTP | `test_http_routes_compatibility.py` com 5 testes; mappers.py condicionais para 5 módulos | Sim, revertendo testes e runtime.md |
| 2026-06-14 | Contrato messaging/worker definido | Padronizar Outbox/Inbox flow: consumer salva Inbox antes ack, processor idempotente, dispatcher pós-commit | `test_outbox_inbox_flow.py` com 5 testes de contrato; `test_worker_locations.py` confirmado | Sim, revertendo testes e runtime.md |
| 2026-06-14 | Database ownership inventory criado | Classificar todas as FKs como intra/cross, catalogar legacy schemas | `test_no_cross_module_foreign_keys.py` com 3 testes; `database-ownership.md` com inventário completo | Sim, revertendo inventário e runtime.md |
| 2026-06-14 | Runtime protocol definido | Estabelecer protocolo operacional: pending/in_progress/completed/blocked, uma spec por commit, shim antes de remoção, allowlist com removal_spec | `test_runtime_manifest_consistency.py` com 6 testes de consistência | Sim, revertendo testes e runtime.md |
| 2026-06-14 | File inventory gerado | Produzir mapa completo de arquivos por módulo antes de qualquer movimentação física | `files.md` com 284 source files; `test_inventory_artifacts.py` com 9 testes; `find` Unix indisponível (substituído por Get-ChildItem) | Sim, revertendo files.md e test |
| 2026-06-14 | Current-to-target structure matrix gerado | Mapear current path → canonical path → action para cada módulo antes de mover arquivos | `structure-matrix.md` com 7 módulos mapeados; agent canônico, demais com dezenas de gaps | Sim, revertendo structure-matrix.md |
| 2026-06-14 | Import dependency map gerado | Catalogar imports intra/inter módulos e camadas antes de mover arquivos | `imports.md` com grafo de imports; `rg` indisponível (Select-String); import_graph.py não encontrado; 1 cross-module production import (agent → identity) identified | Sim, revertendo imports.md |
| 2026-06-14 | Database ownership inventory atualizado | Verificar e estender inventário de FKs e schemas contra branch atual | `database-ownership.md` estendido; migration schemas inventory adicionado; 3 schemas legados (ai, knowledge, runtime) pendentes de migração | Sim, revertendo database-ownership.md |
| 2026-06-14 | Route-controller-composer inventory criado | Mapear rota→composer→controller→use case antes de mover presentation | `routes.md` com ~100 rotas mapeadas; agent com 4 routers legacy+canônico; todos modules seguem mesmo padrão composer/controller | Sim, revertendo routes.md |
| 2026-06-14 | Transaction/UoW inventory catalogado | Catalogar UoW classes, commit/rollback call sites, e coordenação de repositories antes de migrar agent para AgentUnitOfWork e criar UoW específicos por módulo | `transactions.md` com classificação completa; 89 compositores usando PostgresUnitOfWork genérico; agent com AgentUnitOfWork + PostgresUnitOfWork redundantes; 6 módulos sem UoW próprio | Sim, revertendo transactions.md |
| 2026-06-14 | Event/Outbox/Inbox catalog catalogado | Catalogar event_types, routing_keys, Outbox/Inbox models e publishers antes de padronizar envelopes e versionamento | `events.md` com ~65 arquivos analisados; 19 event_types catalogados; agent-only versioned events; 3 namespace legados (ai/knowledge/runtime) ainda em uso | Sim, revertendo events.md |
| 2026-06-14 | Worker/registry inventory catalogado | Catalogar workers, registries e runner antes de criar workers por módulo e wire central | `workers.md` com 26 arquivos; apenas agent tem workers reais; 5 módulos com registries vazios; core sem workers dir; AskJobWorker cruza módulos | Sim, revertendo workers.md |
| 2026-06-14 | Tests/bootstrap/config inventory catalogado | Catalogar tests, main.py, Alembic e pyproject.toml antes de migrar bootstrap e config | `tests-bootstrap.md` com 150 test files, 14 migrações, main.py com 7 módulos de rotas; e2e dir vazio; wildcard imports frágeis em env.py | Sim, revertendo tests-bootstrap.md |
| 2026-06-14 | Risk register and execution order criado | Consolidar 10 inventários em registro de riscos e ordem executável | `risks.md` com 25 riscos; ordem em 9 fases (agent baseline → 6 módulos → transversal → final); 5 riscos críticos, 12 altos, 6 médios, 2 baixos | Sim, revertendo risks.md |
| 2026-06-14 | Agent auditado como referência canônica | Validar agent como template antes de padronizar demais módulos | 19 testes de auditoria e arquitetura criados; 0 imports legados; 90 PostgresUnitOfWork catalogados (deferidos para spec 025); `find`/`rg` Unix indisponíveis (substituídos por Get-ChildItem/Select-String) | Sim, revertendo testes e runtime.md |
| 2026-06-14 | Contratos de domínio do agent normalizados | Completar e validar entities, value objects, events, enums, errors, repositories e services | 13 testes de contratos de domínio + 2 testes de arquitetura adicionados; services.py/value_objects.py mantidos como stubs (sem lógica a adicionar nesta spec); `find`/`rg` indisponíveis (substituídos) | Sim, revertendo testes e runtime.md |
| 2026-06-14 | Application layer do agent normalizada | Separar DTOs, use cases e handlers sem nomes herdados ai/knowledge/runtime como fronteiras | dtos/ e use_cases/ packages com __all__ exports; mappers.py importa de dtos; 10 testes de layout + 3 testes de arquitetura adicionados; ask_agent_stream_service.py e ask_use_case.py allowlistados (infra imports pré-existentes) | Sim, revertendo __init__.py, mappers.py, testes e runtime.md |

## Riscos ativos

| Risco | Severidade | Spec origem | Mitigação | Status |
|---|---|---|---|---|---|
| Padronizar copiando defeitos do agent | alta | 020 | auditar e estabilizar baseline antes dos demais módulos | active |
| FKs cross-module impedirem isolamento | crítica | 013/099 | expand-migrate-contract e IDs opacos | active |
| Rotas quebrarem durante moves | alta | 014/028 | shims temporários e testes de contrato | active |
| Transações permanecerem em UoW genérico | alta | 015/025 | UoW concreto por módulo | active |
| Eventos incompatíveis/duplicados | alta | 016/090-094 | envelope versionado e Inbox idempotente | active |
| 32 legacy schema refs (ai/knowledge/runtime) bloqueiam migração | crítica | 013/099 | expand-migrate-contract + migrate to agent schema | active |
| 89 compositores usam PostgresUnitOfWork genérico | alta | 015/025-036 | migrar para UoW específico por módulo | active |
| AskJobWorker importa de metering/observability (cross-module) | alta | 017/027 | refatorar para event-driven | active |
| Apenas agent tem workers concretos (5 módulos sem workers) | alta | 017/037-087 | criar workers por módulo | active |
| 6 módulos usam event_types sem versionamento | alta | 016/090 | padronizar envelope versionado | active |
| 34 falhas pré-existentes em testes de arquitetura | média | 018/107 | corrigir ou remover na limpeza final | active |
| 25 erros ruff pré-existentes (F821/F401/F841) | baixa | 019/107 | aceitar como pré-existentes, corrigir no cleanup | active |

## Inconsistências encontradas

Registrar aqui divergências entre inventário e premissas das specs.

## Próxima spec recomendada

`023-normalize-agent-composers-and-controllers.md`
