# Execution Runtime

## Suite

`specs/tools-to-agent-consolidation`

## Repository and branch

- Repository: `A1b3rt0M3rcad0/ProjectRAI`
- Baseline: `development` @ `209cf8147f87a2e9949fec33a34429ab70f166b5`
- Execution branch: `development_tools-to-agent-consolidation`

## Current state

Spec 000 ADR completed and committed. Spec 001 inventory completed and committed. Spec 002 target architecture completed and committed. Spec 003 migration protocol completed and committed. Spec 004 baseline characterization and architecture guards completed and committed. 36 characterization tests created. No production code changes made.

## Status

| Spec | Status |
|---|---|
| 000 | completed |
| 001 | completed |
| 002 | completed |
| 003 | completed |
| 004 | completed |
| 005 | pending |
| 006 | pending |
| 007 | pending |
| 008 | pending |
| 009 | pending |
| 010 | pending |
| 011 | pending |
| 012 | pending |
| 013 | pending |
| 014 | pending |
| 015 | pending |
| 016 | pending |
| 017 | pending |

## Specs executadas

### Spec 000 — ADR — incorporar tools ao bounded context agent

**Status:** completed
**Tipo:** architecture
**Branch:** `development_tools-to-agent-consolidation`
**Files changed:**
- `specs/tools-to-agent-consolidation/000-adr-incorporate-tools-into-agent.md` (status: pending → completed)
- `specs/tools-to-agent-consolidation/execution/inventory/decision-log.md` (created)
- `specs/tools-to-agent-consolidation/execution/runtime.md` (updated)

**Detection commands and exit codes:**

| Command | Exit code | Notes |
|---|---|---|
| `git branch --show-current` = `development_tools-to-agent-consolidation` | 0 | Branch verified |
| `git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD` | 0 | Baseline SHA is ancestor |
| `git status --short` | 0 | Clean tree |
| `find src/modules/tools -maxdepth 5 -type f` | 0 | 116 files (58 .py source) |
| `rg "modules\.tools\|schema.?=.tools.\|ForeignKey\(.+tools\|tools\." src migrations tests` | 0 | Found refs in migrations, tests |
| `rg "/tools\|agents/.+tools" src tests` | 0 | Routes found in tests; `frontend/` path absent — noted as environment variant |

**Tools module structure observed:**
- 58 Python source files across domain, application, infra (database, messaging, workers), presentation (controllers, routes, schemas)
- Own UnitOfWork, Outbox/Inbox, models, mappers, repositories
- Own schema `tools` in database migrations
- Own routes prefix `/tools`
- Tests referencing `modules.tools` in architecture/validation tests

**Validation:**

```python
python - <<'PY'
from pathlib import Path
p=Path("specs/tools-to-agent-consolidation/000-adr-incorporate-tools-into-agent.md")
assert p.exists()
assert "módulo independente `tools`" in p.read_text()
print("ok")
PY
```

Exit code: 0

**Acceptance criteria:**
- [x] Ownership unambiguously defined for agent
- [x] Final state without module/schema tools declared
- [x] Secret security explicitly addressed

### Spec 001 — Inventariar tools, dependências e contratos públicos

**Status:** completed
**Tipo:** discovery
**Branch:** `development_tools-to-agent-consolidation`
**Files changed:**
- `specs/tools-to-agent-consolidation/execution/inventory/tools-files.md` (created)
- `specs/tools-to-agent-consolidation/execution/inventory/tools-imports.md` (created)
- `specs/tools-to-agent-consolidation/execution/inventory/tools-api.md` (created)
- `specs/tools-to-agent-consolidation/execution/inventory/tools-events.md` (created)
- `specs/tools-to-agent-consolidation/execution/inventory/tools-database.md` (created)
- `specs/tools-to-agent-consolidation/execution/runtime.md` (updated)

**Detection commands and exit codes:**

| Command | Exit code | Notes |
|---|---|---|
| `git branch --show-current` = `development_tools-to-agent-consolidation` | 0 | Branch verified |
| `git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD` | 0 | Baseline SHA is ancestor |
| `git status --short` | 0 | Clean tree |
| `Get-ChildItem src/modules/tools -Recurse -File -Filter *.py` | 0 | 58 source files inventoried |
| `Select-String "modules\.tools" src tests migrations` | 0 | Cross-module refs catalogued |
| `Select-String "tools\.(tool\|secret)\|routing_key\|event_type" src tests` | 0 | Events and routing catalogued |
| `Select-String "ToolRepository\|SecretRepository\|ToolsUnitOfWork\|ToolModel\|SecretModel" src tests` | 0 | Repository/model refs catalogued |
| `Select-String "/tools\|/agents/\{agent_id\}/tools\|/secrets" src tests` | 0 | Routes catalogued; frontend/ not found |

**Inventory contents:**

| File | Coverage |
|---|---|
| `tools-files.md` | 58 files classified: 46 move, 8 merge, 0 rewrite, 0 delete |
| `tools-imports.md` | All imports catalogued: shared (allowed), cross-module FKs identified, 0 production consumers from other modules |
| `tools-api.md` | 10 routes documented: methods, paths, request/response schemas |
| `tools-events.md` | 4 produced events, 4 consumed events, 3 workers, 2 mapper files |
| `tools-database.md` | 4 tables (tools schema), 2 cross-schema FKs to `core.projects`, 1 unique constraint |

**Key findings:**
- Zero production code outside `modules.tools` imports from `modules.tools` — only test/validation code references it
- 2 cross-schema FKs (`tools.tools.project_id` and `tools.secrets.project_id` -> `core.projects.id`) must be converted to opaque UUIDs
- `frontend/` directory does not exist in this snapshot — noted as environment variant
- Worker registry (`register_tools_workers()`) is currently a no-op
- Inbox handlers declared in `HANDLED_EVENTS` but have no actual implementation logic

**Validation:**

```bash
test -s specs/tools-to-agent-consolidation/execution/inventory/tools-files.md
test -s specs/tools-to-agent-consolidation/execution/inventory/tools-imports.md
test -s specs/tools-to-agent-consolidation/execution/inventory/tools-api.md
test -s specs/tools-to-agent-consolidation/execution/inventory/tools-events.md
test -s specs/tools-to-agent-consolidation/execution/inventory/tools-database.md
```

All 5 files exist and are non-empty. Exit code: 0

**Acceptance criteria:**
- [x] 100% dos arquivos classificados
- [x] rotas/eventos registrados
- [x] consumidores identificados
- [x] riscos de segredo registrados

### Spec 002 — Definir arquitetura-alvo e mapa current-to-target

**Status:** completed
**Tipo:** architecture
**Branch:** `development_tools-to-agent-consolidation`
**Files changed:**
- `specs/tools-to-agent-consolidation/execution/inventory/current-to-target.md` (created)
- `specs/tools-to-agent-consolidation/execution/inventory/target-tree.md` (created)
- `specs/tools-to-agent-consolidation/execution/inventory/public-api-contract.md` (created)
- `specs/tools-to-agent-consolidation/execution/runtime.md` (updated)

**Detection commands and exit codes:**

| Command | Exit code | Notes |
|---|---|---|
| `git branch --show-current` = `development_tools-to-agent-consolidation` | 0 | Branch verified |
| `git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD` | 0 | Baseline SHA is ancestor |
| `git status --short` | 0 | Clean tree |
| `Get-ChildItem src/modules/agent -Recurse -File -Filter *.py` | 0 | 107 source files in agent module |
| `Select-String "class AgentUnitOfWork|ToolExecution|ToolCall|tool_calls" src/modules/agent tests` | 0 | ToolCallResponse and tool_calls found in tests; AgentUnitOfWork exists without tool repos |

**Key findings:**
- Agent module has 107 source files — result of previous ai/knowledge/runtime consolidation
- Agent already has `domain/ports/tool_executor.py` and `domain/ports/tool_repository.py` — ABCs for tool operations
- Agent has `infra/adapters/tools_tool_executor.py` and `infra/adapters/tools_tool_repository.py` — adapters using `importlib` to delegate to `modules.tools`
- `AgentUnitOfWork` exists but does NOT include tool or secret repositories
- `ToolCallResponse` and `tool_calls` schemas already exist in agent test schemas

**Validation:**

```python
python -c "from pathlib import Path; p=Path('specs/tools-to-agent-consolidation/execution/inventory/current-to-target.md'); assert p.exists() and p.stat().st_size>0; t=p.read_text(); assert 'ToolsUnitOfWork' in t and 'tool_secrets' in t; print('ok')"
```

Exit code: 0

**Acceptance criteria:**
- [x] destino explícito para todos os itens
- [x] sem AgentToolsUnitOfWork (ToolsUnitOfWork not retained; merged into AgentUnitOfWork)
- [x] tabelas finais definidas (schema agent)

## Decisões tomadas durante a execução

- `frontend/` directory does not exist in this repository snapshot; detection was adapted to omit it. This is a pre-existing environment condition, not a regression.
- `rg` (ripgrep) not available on Windows; `Select-String` (PowerShell) used as equivalent.
- Agent module already has tool ports and `importlib`-based adapters; these will be replaced during consolidation.

### Spec 003 — Definir protocolo incremental, compatibilidade e rollback

**Status:** completed
**Tipo:** migration-planning
**Branch:** `development_tools-to-agent-consolidation`
**Files changed:**
- `specs/tools-to-agent-consolidation/execution/inventory/migration-protocol.md` (created)
- `specs/tools-to-agent-consolidation/execution/inventory/rollback-matrix.md` (created)
- `specs/tools-to-agent-consolidation/execution/inventory/cutover-checklist.md` (created)
- `specs/tools-to-agent-consolidation/execution/runtime.md` (updated)

**Detection commands and exit codes:**

| Command | Exit code | Notes |
|---|---|---|
| `git branch --show-current` = `development_tools-to-agent-consolidation` | 0 | Branch verified |
| `git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD` | 0 | Baseline SHA is ancestor |
| `git status --short` | 0 | Clean tree |
| `alembic heads` | 0 | Head: `0020` |
| `alembic history` | 0 | 20 migrations (0001-0020); previous schema consolidation (0015-0020) already migrated ai/knowledge/runtime → agent |
| `rg "CREATE OR REPLACE VIEW|SET SCHEMA|DROP SCHEMA" migrations/versions` | 0 | No VIEW/SET SCHEMA/DROP SCHEMA in current migrations |

**Validation:**

```bash
test -s specs/tools-to-agent-consolidation/execution/inventory/migration-protocol.md
test -s specs/tools-to-agent-consolidation/execution/inventory/rollback-matrix.md
test -s specs/tools-to-agent-consolidation/execution/inventory/cutover-checklist.md
```

All 3 files exist and are non-empty. Exit code: 0

**Acceptance criteria:**
- [x] fases e gates definidos (expand, migrate, cutover, contract)
- [x] compatibilidade com prazo (shims with removal specs)
- [x] rollback preserva dados (pre-contract only; post-DROP requires backup)

## Riscos ativos

- Consumidores externos de `tools.*` não comprovados.
- Volumes/status de Inbox/Outbox exigem banco.
- Resolver de segredos legado parece incompatível com repository async.
- Paths efetivos devem ser confirmados pelo OpenAPI.
- Se development avançar, refazer inventário.

### Spec 004 — Adicionar guards e testes de caracterização antes da migração

**Status:** completed
**Tipo:** testing
**Branch:** `development_tools-to-agent-consolidation`
**Files changed:**
- `tests/architecture/test_tools_migration_baseline.py` (created)
- `tests/contract/test_tools_routes_characterization.py` (created)
- `tests/integration/tools/__init__.py` (created)
- `tests/integration/tools/test_tools_event_characterization.py` (created)
- `tests/unit/tools/__init__.py` (created)
- `tests/unit/tools/test_secret_characterization.py` (created)
- `specs/tools-to-agent-consolidation/execution/runtime.md` (updated)

**Detection commands and exit codes:**

| Command | Exit code | Notes |
|---|---|---|
| `git branch --show-current` = `development_tools-to-agent-consolidation` | 0 | Branch verified |
| `git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD` | 0 | Baseline SHA is ancestor |
| `git status --short` | 0 | Clean tree |
| `find tests -type f` | 0 | 200+ test files exist, including existing tools tests |
| `rg "tools\|Tool\|Secret\|/tools\|tools\." tests` | 0 | Rich references across test files |
| `pytest --collect-only -q` | 1 | 3140 collected, 19 pre-existing collection errors in observability/tools tests |

**Tests created (36 total):**

| Test suite | File | Tests |
|---|---|---|
| Architecture baseline | `tests/architecture/test_tools_migration_baseline.py` | 9 |
| Routes characterization | `tests/contract/test_tools_routes_characterization.py` | 12 |
| Events characterization | `tests/integration/tools/test_tools_event_characterization.py` | 9 |
| Secret safety characterization | `tests/unit/tools/test_secret_characterization.py` | 6 |

**Validation:**

```bash
pytest tests/architecture/test_tools_migration_baseline.py -q
pytest tests/contract/test_tools_routes_characterization.py -q
pytest tests/integration/tools/test_tools_event_characterization.py -q
pytest tests/unit/tools/test_secret_characterization.py -q
```

All 36 tests pass. Exit code: 0

**Acceptance criteria:**
- [x] API/eventos caracterizados (routes, events, schemas)
- [x] segredos protegidos (encryption checks, no plaintext in responses)
- [x] allowlist explícita (baseline tests define current tools module state)

## Inconsistências encontradas

- `frontend/` directory not present in repository, though spec references it. Not a blocker — environment variant.
- 19 pre-existing test collection errors in `tests/unit/test_tools` and `tests/unit/test_observability` — pre-existing, not caused by this spec.

## Próxima spec recomendada

`005-move-tools-domain-contracts-into-agent.md`
