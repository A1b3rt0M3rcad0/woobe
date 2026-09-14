from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "packages" / "woobe-frontend" / "src"
AGENT_FEATURE = FRONTEND / "features" / "agents"
PLAYGROUND = FRONTEND / "features" / "playground"
API_ROUTES = (
    ROOT
    / "packages"
    / "woobe-api"
    / "src"
    / "woobe_api"
    / "http"
    / "agent"
    / "execution_strategy_routes.py"
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_execution_runtime_settings_use_backend_strategy_catalog() -> None:
    field = _source(AGENT_FEATURE / "components" / "AgentExecutionStrategyField.tsx")
    runtime = _source(AGENT_FEATURE / "components" / "AgentRuntimeSettings.tsx")

    assert "useExecutionStrategies" in field
    assert "executionStrategySelectOptions" in field
    assert "<Select" in field
    assert "withExecutionStrategy" in field
    assert "<AgentExecutionStrategyField" in runtime


def test_playground_exposes_draft_strategy_selection_but_locks_snapshots() -> None:
    header = _source(PLAYGROUND / "components" / "PlaygroundHeader.tsx")

    assert "Playground Execution Strategy" in header
    assert "useExecutionStrategies" in header
    assert "useAgentEditor" in header
    assert "useReleases" in header
    assert "withExecutionStrategy" in header
    assert "strategyReadOnly = environment !== 'draft'" in header
    assert "immutableRelease?.runtime_config" in header
    assert "if (strategyReadOnly" in header


def test_frontend_and_backend_share_execution_strategy_catalog_endpoint() -> None:
    frontend_api = _source(AGENT_FEATURE / "api.ts")
    backend_route = _source(API_ROUTES)

    assert "'/ai/execution-strategies'" in frontend_api
    assert '"/execution-strategies"' in backend_route
    assert "list_execution_strategies" in backend_route
