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
last_validated_sha: c128cb06372ecd0d748a144a91093ca3417a590c
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
| 005 | pending | - | - | - | 006 |
| 006 | pending | - | - | - | 007 |
| 007 | pending | - | - | - | 008 |
| 008 | pending | - | - | - | 009 |
| 009 | pending | - | - | - | 010 |
| 010 | pending | - | - | - | 011 |
| 011 | pending | - | - | - | 012 |
| 012 | pending | - | - | - | 013 |
| 013 | pending | - | - | - | 014 |
| 014 | pending | - | - | - | 015 |
| 015 | pending | - | - | - | 016 |
| 016 | pending | - | - | - | 017 |
| 017 | pending | - | - | - | 018 |
| 018 | pending | - | - | - | 019 |
| 019 | pending | - | - | - | 020 |
| 020 | pending | - | - | - | 021 |
| 021 | pending | - | - | - | 022 |
| 022 | pending | - | - | - | 023 |
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

## Specs pendentes

Specs 005 a 109 do `MANIFEST.md`.

## Decisões tomadas durante a execução

| Data | Decisão | Motivo | Impacto | Reversível? |
|---|---|---|---|---|
| 2026-06-14 | ADR canônico registrado e aceito | Estabelecer base arquitetural obrigatória antes de qualquer migração física | Todos os módulos devem seguir o mesmo contrato estrutural; proibição de FK e imports cross-module | Sim, revertendo o ADR e runtime.md |
| 2026-06-14 | Regras de dependência por camada definidas | Especificar imports permitidos/proibidos por camada antes de mover arquivos | Layer test + AST scan + allowlist com scope layer_dependencies; composers exempt por serem raiz de DI | Sim, removendo regras e allowlist |
| 2026-06-14 | Estrutura canônica de diretórios definida | Padronizar responsabilidades sem criar abstrações vazias | `test_module_structure.py` com 4 testes; domain files obrigatórios vs condicionais; agent infra canônica vs outros com infra plana | Sim, revertendo teste e doc |
| 2026-06-14 | API pública dos módulos definida via __init__.py | Bootstrap, workers e rotas acessam módulos sem importar internals | Todos os 7 módulos expõem routes e registry via __all__; 5 testes de entrypoint | Sim, revertendo __init__.py e teste |
| 2026-06-14 | Contratos domain/application definidos | Use cases não importam FastAPI/SQLAlchemy; composers sem lógica de domínio; DTOs fora de shared | `test_application_boundaries.py` com 3 testes; 2 allowlist entries para sqlalchemy em use_cases | Sim, revertendo teste e allowlist |

## Riscos ativos

| Risco | Severidade | Spec origem | Mitigação | Status |
|---|---|---|---|---|
| Padronizar copiando defeitos do agent | alta | 020 | auditar e estabilizar baseline antes dos demais módulos | active |
| FKs cross-module impedirem isolamento | crítica | 013/099 | expand-migrate-contract e IDs opacos | active |
| Rotas quebrarem durante moves | alta | 014 | shims temporários e testes de contrato | active |
| Transações permanecerem em UoW genérico | alta | 015/025 | UoW concreto por módulo | active |
| Eventos incompatíveis/duplicados | alta | 016/090-094 | envelope versionado e Inbox idempotente | active |

## Inconsistências encontradas

Registrar aqui divergências entre inventário e premissas das specs.

## Próxima spec recomendada

`005-define-infrastructure-database-and-uow-contract.md`
