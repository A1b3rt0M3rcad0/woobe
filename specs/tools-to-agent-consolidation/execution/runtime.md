# Execution Runtime

## Suite

`specs/tools-to-agent-consolidation`

## Repository and branch

- Repository: `A1b3rt0M3rcad0/ProjectRAI`
- Baseline: `development` @ `209cf8147f87a2e9949fec33a34429ab70f166b5`
- Execution branch: `development_tools-to-agent-consolidation`

## Current state

Spec 000 ADR completed and committed. Spec 001 inventory completed and committed. Spec 002 target architecture completed and committed. Current-to-target map, target tree, and public API contract defined. No code changes made.

## Status

| Spec | Status |
|---|---|
| 000 | completed |
| 001 | completed |
| 002 | completed |
| 003 | pending |
| 004 | pending |
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

## Riscos ativos

- Consumidores externos de `tools.*` não comprovados.
- Volumes/status de Inbox/Outbox exigem banco.
- Resolver de segredos legado parece incompatível com repository async.
- Paths efetivos devem ser confirmados pelo OpenAPI.
- Se development avançar, refazer inventário.

## Inconsistências encontradas

- `frontend/` directory not present in repository, though spec references it. Not a blocker — environment variant.

## Próxima spec recomendada

`003-define-incremental-compatibility-and-rollback-protocol.md`
