from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INVOKER_FILE = PROJECT_ROOT / "src/modules/network/infra/runtime/agent_invoker.py"

FORBIDDEN_AGENT_INTERNALS = {
    "AgentToolRuntimeGateway",
    "LangchainEmbeddingFactory",
    "LangchainLLMFactory",
    "StructuredOutputAskAgentUseCase",
}
FORBIDDEN_DATABASE_TYPES = {
    "AsyncEngine",
    "AsyncSession",
    "async_sessionmaker",
}


def test_network_agent_invoker_uses_public_runtime_composition_boundary() -> None:
    source = INVOKER_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(INVOKER_FILE))

    agent_entrypoint_imports: set[str] = set()
    database_imports: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        imported = {alias.asname or alias.name for alias in node.names}
        if node.module == "modules.agent.entrypoint":
            agent_entrypoint_imports.update(imported)
        if node.module == "sqlalchemy.ext.asyncio":
            database_imports.update(imported)

    assert "build_internal_agent_runtime" in agent_entrypoint_imports
    assert not agent_entrypoint_imports.intersection(FORBIDDEN_AGENT_INTERNALS)
    assert not database_imports.intersection(FORBIDDEN_DATABASE_TYPES)
    assert "_engine_from_session_factory" not in source
    assert "session_factory=" not in source
