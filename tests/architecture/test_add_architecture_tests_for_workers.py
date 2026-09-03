"""Focused rejection tests for the worker ownership rules."""
from __future__ import annotations

import ast


def _imports(source: str) -> set[str]:
    tree = ast.parse(source)
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
        elif isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
    return result


def test_detects_core_to_worker_host_dependency() -> None:
    imports = _imports("from woobe_workers.runtime.runner import WorkerRunner\n")
    assert any(name.startswith("woobe_workers") for name in imports)


def test_detects_consumer_bypassing_public_boundary() -> None:
    imports = _imports(
        "from modules.agent.infra.database.repositories import SQLAlchemyAgentRepository\n"
    )
    assert any(name.startswith("modules.agent.infra") for name in imports)


def test_accepts_consumer_using_public_background_boundary() -> None:
    imports = _imports(
        "from modules.agent.background_boundary import SQLAlchemyAgentRepository\n"
    )
    assert imports == {"modules.agent.background_boundary"}
