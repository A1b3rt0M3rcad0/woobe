from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "packages" / "woobe-frontend" / "src"
AGENT_FEATURE = FRONTEND / "features" / "agents"
PLAYGROUND = FRONTEND / "features" / "playground"
API_AGENT_ROOT = (
    ROOT
    / "packages"
    / "woobe-api"
    / "src"
    / "woobe_api"
    / "http"
    / "agent"
)
API_ROUTES = API_AGENT_ROOT / "execution_strategy_routes.py"
API_INIT = API_AGENT_ROOT / "__init__.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_execution_runtime_settings_use_backend_strategy_catalog() -> None:
    field = _source(AGENT_FEATURE / "components" / "AgentExecutionStrategyField.tsx")
    runtime = _source(AGENT_FEATURE / "components" / "AgentRuntimeSettings.tsx")

    assert "useExecutionStrategies" in field
    assert "executionStrategyDescriptor" in field
    assert "withExecutionStrategy" in field
    assert "<Dialog" in field
    assert 'title="Select Execution Strategy"' in field
    assert "recommended_for" in field
    assert "capabilities" in field
    assert "limitations" in field
    assert "Runtime boundary" in field
    assert "<AgentExecutionStrategyField" in runtime
    assert "useExecutionStrategies" in runtime
    assert "executionStrategyDescriptor" in runtime


def test_knowledge_manager_uses_shared_workspace_dialog() -> None:
    knowledge = _source(PLAYGROUND / "components" / "ManageKnowledgeModal.tsx")

    assert "from '@woobe/ui'" in knowledge
    assert "<Dialog" in knowledge
    assert 'variant="workspace"' in knowledge
    assert 'height="workspace"' in knowledge
    assert "<DialogContextBar>" in knowledge
    assert "<DialogFooter" in knowledge
    assert "CollectionDetailsModal" in knowledge
    assert "CreateCollectionModal" in knowledge
    assert "fixed inset-0" not in knowledge


def test_playground_exposes_draft_strategy_selection_but_locks_snapshots() -> None:
    header = _source(PLAYGROUND / "components" / "PlaygroundHeader.tsx")
    strategy_helpers = _source(AGENT_FEATURE / "executionStrategy.ts")

    assert "Playground Execution Strategy" in header
    assert "useExecutionStrategies" in header
    assert "useAgentEditor" in header
    assert "useReleases" in header
    assert "executionStrategyForEnvironment" in header
    assert "withExecutionStrategy" in header
    assert "strategyReadOnly = environment !== 'draft'" in header
    assert "if (strategyReadOnly" in header
    assert "if (environment === 'draft')" in strategy_helpers
    assert "releases.find((item) => item.status === environment)" in strategy_helpers
    assert "release?.runtime_config" in strategy_helpers


def test_frontend_and_backend_share_execution_strategy_catalog_endpoint() -> None:
    frontend_api = _source(AGENT_FEATURE / "api.ts")
    backend_route = _source(API_ROUTES)
    api_init = _source(API_INIT)

    assert "'/ai/execution-strategies'" in frontend_api
    assert '"/execution-strategies"' in backend_route
    assert "list_execution_strategies" in backend_route
    assert "execution_strategy_router" in api_init
    assert "execution_strategy_router," in api_init
