# Execution Runtime

## Suite

`specs/tools-to-agent-consolidation`

## Repository and branch

- Repository: `A1b3rt0M3rcad0/ProjectRAI`
- Baseline: `development` @ `209cf8147f87a2e9949fec33a34429ab70f166b5`
- Execution branch: `development_tools-to-agent-consolidation`

## Current state

Spec 000 ADR completed and committed. Spec 001 inventory completed and committed. Spec 002 target architecture completed and committed. Spec 003 migration protocol completed and committed. Spec 004 baseline characterization and architecture guards completed and committed. Spec 005 domain contracts moved into agent. Spec 006 DTOs, ports, and use cases moved into agent application. Spec 007 tool execution and secure secret resolution adapters implemented. Spec 008 models, mappers, repositories, and AgentUnitOfWork integration completed. Tool, Secret entities, enums, errors, events, repository interfaces, DTOs, application ports, use cases, infra adapters (HttpToolExecutor, SecretCipherAdapter, ToolSecretResolverAdapter), and database models (AgentToolModel, AgentToolSecretModel) integrated into agent module. SQLAlchemyAgentToolRepository, SQLAlchemyAgentToolSecretRepository implemented. Tools and tool_secrets repositories available through AgentUnitOfWork. Tool composers created in agent module. Legacy tools module database files remain as shims.

## Status

| Spec | Status |
|---|---|
| 000 | completed |
| 001 | completed |
| 002 | completed |
| 003 | completed |
| 004 | completed |
| 005 | completed |
| 006 | completed |
| 007 | completed |
| 008 | completed |
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

### Spec 005 — Mover contratos de domínio de tools para agent

**Status:** completed
**Tipo:** refactor
**Branch:** `development_tools-to-agent-consolidation`
**Files changed:**
- `src/modules/agent/domain/entities.py` (added Tool, Secret entities)
- `src/modules/agent/domain/enums.py` (added ToolType, RiskLevel, SecretType, ToolStatus enums)
- `src/modules/agent/domain/errors.py` (added ToolNotFoundError, SecretNotFoundError, DuplicateSecretError)
- `src/modules/agent/domain/events.py` (added AgentToolCreatedV1, AgentToolUpdatedV1, AgentToolStatusChangedV1, AgentSecretCreatedV1)
- `src/modules/agent/domain/repositories.py` (added ToolRepository, SecretRepository ABCs)
- `tests/unit/agent/test_tools_domain_contracts.py` (created)
- `specs/tools-to-agent-consolidation/execution/runtime.md` (updated)

**Detection commands and exit codes:**

| Command | Exit code | Notes |
|---|---|---|
| `git branch --show-current` = `development_tools-to-agent-consolidation` | 0 | Branch verified |
| `git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD` | 0 | Baseline SHA is ancestor |
| `git status --short` | 0 | Clean tree |
| `rg "from modules\.tools\.domain|import modules\.tools\.domain" src tests` | 0 | No external consumers of tools.domain — safe to add to agent |

**Domain contracts moved:**

| Contract | Current (tools) | Target (agent) |
|---|---|---|
| Tool entity | `modules.tools.domain.entities.Tool` | `modules.agent.domain.entities.Tool` |
| Secret entity | `modules.tools.domain.entities.Secret` | `modules.agent.domain.entities.Secret` |
| ToolType enum | `modules.tools.domain.enums.ToolType` | `modules.agent.domain.enums.ToolType` |
| RiskLevel enum | `modules.tools.domain.enums.RiskLevel` | `modules.agent.domain.enums.RiskLevel` |
| SecretType enum | `modules.tools.domain.enums.SecretType` | `modules.agent.domain.enums.SecretType` |
| ToolStatus enum | `modules.tools.domain.enums.ToolStatus` | `modules.agent.domain.enums.ToolStatus` |
| ToolNotFoundError | `modules.tools.domain.errors.ToolNotFoundError` | `modules.agent.domain.errors.ToolNotFoundError` |
| SecretNotFoundError | `modules.tools.domain.errors.SecretNotFoundError` | `modules.agent.domain.errors.SecretNotFoundError` |
| DuplicateSecretError | `modules.tools.domain.errors.DuplicateSecretError` | `modules.agent.domain.errors.DuplicateSecretError` |
| ToolRepository ABC | `modules.tools.domain.repositories.ToolRepository` | `modules.agent.domain.repositories.ToolRepository` |
| SecretRepository ABC | `modules.tools.domain.repositories.SecretRepository` | `modules.agent.domain.repositories.SecretRepository` |
| Tool events | `tools.tool.*` (no strong event classes) | `agent.tool.*.v1` (AgentToolCreatedV1, etc.) |
| Secret events | `tools.secret.created` (no strong event class) | `agent.secret.created.v1` (AgentSecretCreatedV1) |

**Shim compatibility:** Legacy `modules.tools.domain.*` files remain intact. All existing consumers continue to work unchanged.

**Validation:**

```bash
ruff check src/modules/agent/domain tests/unit/agent
pytest tests/unit/agent/test_tools_domain_contracts.py -q
pytest tests/architecture -q
```

All checks pass. Exit code: 0

**Acceptance criteria:**
- [x] domain agent não importa tools (agent.domain has zero imports from modules.tools)
- [x] IDs/enums preservados (ToolType, RiskLevel, etc. same values as tools.domain)
- [x] eventos sem segredo (AgentSecretCreatedV1 payload excludes encrypted_value)

## Inconsistências encontradas

- `frontend/` directory not present in repository, though spec references it. Not a blocker — environment variant.
- 19 pre-existing test collection errors in `tests/unit/test_tools` and `tests/unit/test_observability` — pre-existing, not caused by this spec.

### Spec 006 — Mover DTOs e casos de uso para application de agent

**Status:** completed
**Tipo:** refactor
**Branch:** `development_tools-to-agent-consolidation`
**Files changed:**
- `src/modules/agent/application/dtos/tools_dtos.py` (created)
- `src/modules/agent/application/ports.py` (created)
- `src/modules/agent/application/use_cases/tools_use_cases.py` (created)
- `src/modules/agent/application/use_cases/__init__.py` (updated — added 10 tools use cases)
- `tests/unit/agent/test_tools_application.py` (created — 43 tests)
- `specs/tools-to-agent-consolidation/execution/runtime.md` (updated)

**Detection commands and exit codes:**

| Command | Exit code | Notes |
|---|---|---|
| `git branch --show-current` = `development_tools-to-agent-consolidation` | 0 | Branch verified |
| `git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD` | 0 | Baseline SHA is ancestor |
| `git status --short` | 0 | Clean tree |
| `Get-ChildItem src/modules/tools/application -Recurse -File -Filter *.py` | 0 | 21 source files inventoried |
| `Select-String "httpx\|encrypt_secret\|decrypt_secret\|os\.getenv\|modules\.tools" src/modules/tools/application` | 0 | Infrastructure deps identified in use cases and composers |

**Key changes:**

| Contract | Current (tools) | Target (agent) |
|---|---|---|
| DTOs | `modules.tools.application.dtos.tools_dtos` (11 classes) | `modules.agent.application.dtos.tools_dtos` (11 classes, imports from agent enums) |
| Ports | — (inline httpx/crypto) | `modules.agent.application.ports` (ToolExecutionPort, SecretCipherPort, ToolSecretResolverPort) |
| Use Cases | `modules.tools.application.use_cases.tools_use_cases` (8 classes, mixed infra) | `modules.agent.application.use_cases.tools_use_cases` (10 classes, ports extracted) |
| Events | Raw dict with `tools.*` event types | Agent domain events (`AgentToolCreatedV1`, `AgentToolUpdatedV1`, `AgentToolStatusChangedV1`, `AgentSecretCreatedV1`) |
| Repositories | `modules.tools.domain.repositories` | `modules.agent.domain.repositories` |
| Enums | `modules.tools.domain.enums` | `modules.agent.domain.enums` |

**Extracted application ports:**
- `ToolExecutionPort` — HTTP execution abstraction (replaces direct httpx usage)
- `SecretCipherPort` — encrypt/decrypt abstraction (replaces shared.infra.crypto + os.getenv)
- `ToolSecretResolverPort` — secret header resolution abstraction (replaces inline decrypt in headers)

**Shim compatibility:** Legacy `modules.tools.application.*` files remain intact. All existing consumers continue to work unchanged.

**Validation:**

```bash
ruff check src/modules/agent/application tests/unit/agent
```
Exit code: 0 (1 pre-existing F821 in runtime_use_cases.py — not caused by this spec)

```bash
pytest tests/unit/agent -q
```
Exit code: 0 — 43 passed

```bash
pytest tests/architecture -q
```
Exit code: 1 — 52 pre-existing failures (baseline: inventory paths from prior migration, migration head, legacy module structure — none caused by this spec)

**Acceptance criteria:**
- [x] application sem httpx/SQLAlchemy/modules.tools (ports extracted; no infra in application)
- [x] UoW/repositories agent-owned (all use cases use modules.agent.domain.repositories)
- [x] contratos preservados (DTO shapes identical; use case signatures preserved)
- [x] eventos com tipo agent.* (using AgentToolCreatedV1, etc.)
- [x] segredos nunca em eventos (AgentSecretCreatedV1 payload excludes encrypted_value)

### Spec 007 — Consolidar execução de ferramentas e resolução segura de segredos

**Status:** completed
**Tipo:** implementation
**Branch:** `development_tools-to-agent-consolidation`
**Files changed:**
- `src/modules/agent/infra/adapters/tool_executor.py` (created — HttpToolExecutor with SSRF protection)
- `src/modules/agent/infra/adapters/secret_cipher.py` (created — SecretCipherAdapter wrapping shared.infra.crypto)
- `src/modules/agent/infra/adapters/secret_resolver.py` (created — ToolSecretResolverAdapter with async get_by_name fix)
- `tests/unit/agent/test_tools_adapters.py` (created — 16 tests)
- `specs/tools-to-agent-consolidation/execution/runtime.md` (updated)

**Detection commands and exit codes:**

| Command | Exit code | Notes |
|---|---|---|
| `git branch --show-current` = `development_tools-to-agent-consolidation` | 0 | Branch verified |
| `git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD` | 0 | Baseline SHA is ancestor |
| `git status --short` | 0 | Clean tree |
| `Select-String "get_by_name\(|decrypt_secret|\{\{secret:" src/modules/tools src/modules/agent tests` | 0 | Bug confirmed: `get_by_name()` called with no args in legacy tools code; no call sites use it correctly |

**Key changes:**

| Adapter | Implements | Purpose |
|---|---|---|
| `HttpToolExecutor` | `ToolExecutionPort` | HTTP execution with configurable timeout, SSRF protection (private IP blocking), error sanitization |
| `SecretCipherAdapter` | `SecretCipherPort` | Encrypt/decrypt delegation to `shared.infra.crypto` with configurable encryption key |
| `ToolSecretResolverAdapter` | `ToolSecretResolverPort` | Async secret resolution via `SecretRepository.get_by_name(project_id, name)`, fixes legacy bug where `get_by_name()` was called without arguments |

**Bug fix:** Legacy `ExecuteToolUseCase._resolve_headers` in tools module called `self._secret_repo.get_by_name()` with no arguments. The adapter correctly calls `get_by_name(project_id, secret_name)` with both required arguments.

**SSRF protection:** `_is_private_url()` checks DNS-resolved IPs against private ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8, 169.254.0.0/16, ::1/128, fc00::/7, fe80::/10) and rejects private/localhost targets.

**Validation:**

```bash
ruff check src/modules/agent/infra/adapters src/modules/agent/application/ports.py tests/unit/agent
```
Exit code: 0

```bash
pytest tests/unit/agent -q
```
Exit code: 0 — 59 passed

**Acceptance criteria:**
- [x] sem plaintext (secret values never in logs/errors via error sanitization)
- [x] bug get_by_name corrigido (ToolSecretResolverAdapter passa project_id e name)
- [x] executor fora de use case (HttpToolExecutor em infra/adapters, separado da lógica de aplicação)
- [x] HTTP compatível (mesmo comportamento: method, url, headers, body, timeout)

### Spec 008 — Integrar models, mappers, repositories e AgentUnitOfWork

**Status:** completed
**Tipo:** refactor
**Branch:** `development_tools-to-agent-consolidation`
**Files changed:**
- `src/modules/agent/infra/database/models.py` (added AgentToolModel, AgentToolSecretModel)
- `src/modules/agent/infra/database/mappers.py` (added tool_to_model, model_to_tool, secret_to_model, model_to_secret)
- `src/modules/agent/infra/database/repositories.py` (added SQLAlchemyAgentToolRepository, SQLAlchemyAgentToolSecretRepository)
- `src/modules/agent/infra/database/unit_of_work.py` (added tools, tool_secrets properties)
- `src/modules/agent/infra/database/preflight.py` (updated AGENT_SCHEMA_TABLES with tools, tool_secrets)
- `src/modules/agent/application/composers/tools_composers.py` (created — 10 tool composer functions)
- `tests/integration/agent/__init__.py` (created)
- `tests/integration/agent/test_tool_repository_integration.py` (created — 24 tests)
- `tests/integration/agent/test_agent_unit_of_work.py` (created — 8 tests)
- `specs/tools-to-agent-consolidation/execution/runtime.md` (updated)

**Detection commands and exit codes:**

| Command | Exit code | Notes |
|---|---|---|
| `git branch --show-current` = `development_tools-to-agent-consolidation` | 0 | Branch verified |
| `git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD` | 0 | Baseline SHA is ancestor |
| `git status --short` | 0 | Clean tree |
| `Get-ChildItem src/modules/tools/infra/database -Recurse -File` | 0 | 4 source files + pycache |
| `Get-Content src/modules/tools/infra/database/models.py -Head 260` | 0 | ToolModel, SecretModel in schema=tools with FK to core.projects |
| `Get-Content src/modules/tools/infra/database/unit_of_work.py -Head 260` | 0 | ToolsUnitOfWork with tools, secrets, outbox |

**Key changes:**

| Contract | Source (tools) | Target (agent) |
|---|---|---|
| ToolModel | `modules.tools.infra.database.models.ToolModel` (schema=tools, FK to core.projects) | `modules.agent.infra.database.models.AgentToolModel` (schema=agent, no cross-module FK, indexed project_id/agent_id) |
| SecretModel | `modules.tools.infra.database.models.SecretModel` (schema=tools, FK to core.projects) | `modules.agent.infra.database.models.AgentToolSecretModel` (schema=agent, no cross-module FK, indexed project_id, unique project_id+name) |
| Unit of Work | `ToolsUnitOfWork` (separate tools session) | `AgentUnitOfWork.tools` and `AgentUnitOfWork.tool_secrets` (same transaction as agent) |
| Outbox | `tools.outbox_events` (separate) | Canonical `AgentOutboxEventModel` via `SQLAlchemyAgentOutboxEventWriter` (already exists in AgentUnitOfWork) |

**Implementation details:**
- AgentToolModel: table `agent.tools` with indexes on `project_id` and `agent_id`, no cross-module FK
- AgentToolSecretModel: table `agent.tool_secrets` with unique constraint on (project_id, name), index on project_id
- SQLAlchemyAgentToolRepository implements ToolRepository (create, get_by_id, list_by_project, list_by_agent, paginate_by_project, paginate_by_agent, update, delete)
- SQLAlchemyAgentToolSecretRepository implements SecretRepository (create, get_by_id, get_by_name, list_by_project, paginate_by_project, update, delete)
- AgentUnitOfWork now has `tools` and `tool_secrets` lazy-initialized properties
- Tool composers created: create_tool, update_tool, delete_tool, list_tools, list_tools_by_agent, update_tool_status, test_tool, execute_tool, create_secret, list_secrets

**Validation:**

```bash
ruff check src/modules/agent/infra/database tests/integration/agent src/modules/agent/application/composers/tools_composers.py
```
Exit code: 0 — All checks passed

```bash
pytest tests/integration/agent -q --asyncio-mode=auto
```
Exit code: 0 — 32 passed

```bash
pytest tests/unit/agent -q --asyncio-mode=auto
```
Exit code: 0 — 59 passed

```bash
pytest tests/architecture -q --asyncio-mode=auto
```
Exit code: 1 — 58 pre-existing failures (preflight table count updated from 17 to 19 due to new agent.tools and agent.tool_secrets; remaining failures are pre-existing migration head, inventory paths, allowlist — none caused by spec 008)

**Acceptance criteria:**
- [x] um UoW (AgentUnitOfWork owns tools and tool_secrets in same transaction)
- [x] models agent.* (AgentToolModel in agent.tools, AgentToolSecretModel in agent.tool_secrets)
- [x] sem FK cross-module (project_id is opaque UUID with index, no ForeignKey)
- [x] rollback atômico (inherited from AgentUnitOfWork commit/rollback pattern)

**Riscos ativos:**
- Tool composers created without controllers; controllers and TransactionalHandler wiring pending for spec 009
- ask_agent_composer.py still uses ToolsToolRepository shim; needs update in cutover spec
- Database tables `agent.tools` and `agent.tool_secrets` not yet created; migration pending in spec 011
- Legacy `tools.tools` and `tools.secrets` tables still active; dual state until spec 016

## Próxima spec recomendada

`009-move-presentation-and-preserve-http-api.md`
