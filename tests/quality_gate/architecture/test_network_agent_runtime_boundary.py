from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_ROOT = PROJECT_ROOT / "packages/woobe-core/src"
WORKERS_ROOT = PROJECT_ROOT / "packages/woobe-workers/src"
INVOKER_FILE = (
    WORKERS_ROOT / "woobe_workers" / "composition" / "network_agent_runtime.py"
)
APPLICATION_RUNTIME_FILE = CORE_ROOT / "modules/network/application/runtime.py"
REDIS_STORE_FILE = CORE_ROOT / "modules/network/infra/runtime/redis_store.py"
NETWORK_ROOT = CORE_ROOT / "modules/network"

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


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _import_modules(tree: ast.Module) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def _method(tree: ast.Module, class_name: str, method_name: str) -> ast.AST:
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method_name:
                return child
    raise AssertionError(f"{class_name}.{method_name} was not found")


def _calls_named(node: ast.AST, name: str) -> list[ast.Call]:
    return [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and (
            (isinstance(child.func, ast.Name) and child.func.id == name)
            or (isinstance(child.func, ast.Attribute) and child.func.attr == name)
        )
    ]


def test_network_agent_invoker_is_outer_composition_adapter() -> None:
    source = INVOKER_FILE.read_text(encoding="utf-8")
    tree = _parse(INVOKER_FILE)

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
    assert "session_factory=" not in source


def test_network_core_does_not_own_agent_runtime_adapter() -> None:
    assert not (NETWORK_ROOT / "infra/runtime/agent_invoker.py").exists()
    violations = []
    for path in NETWORK_ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "from modules.agent" in source or "import modules.agent" in source:
            violations.append(path.relative_to(PROJECT_ROOT).as_posix())
    # This gate is intentionally scoped to the runtime bridge in this migration;
    # release/catalog coupling is removed by the broader module-boundary phase.
    runtime_violations = [
        path for path in violations
        if "/infra/runtime/" in path
    ]
    assert not runtime_violations, "Network runtime imports Agent directly:\n" + "\n".join(runtime_violations)


def test_network_agent_runtime_is_process_scoped_not_invocation_scoped() -> None:
    tree = _parse(INVOKER_FILE)
    constructor = _method(tree, "ProjectRAIAgentInvoker", "__init__")
    invoke = _method(tree, "ProjectRAIAgentInvoker", "invoke")
    assert len(_calls_named(constructor, "build_internal_agent_runtime")) == 1
    assert not _calls_named(invoke, "build_internal_agent_runtime")


def test_network_application_runtime_has_no_infrastructure_dependency() -> None:
    source = APPLICATION_RUNTIME_FILE.read_text(encoding="utf-8")
    tree = _parse(APPLICATION_RUNTIME_FILE)
    imports = _import_modules(tree)
    violations = sorted(
        module
        for module in imports
        if module == "sqlalchemy"
        or module.startswith("sqlalchemy.")
        or module.startswith("modules.network.infra")
    )
    assert not violations, "ARCH-NETWORK-RUN-TX-001\n" + "\n".join(violations)
    assert "NetworkExecutionModel" not in source
    assert "NetworkVersionModel" not in source
    assert "NetworkInvocationModel" not in source


def test_network_runtime_uses_frozen_session_mode_without_late_lookup() -> None:
    source = APPLICATION_RUNTIME_FILE.read_text(encoding="utf-8")
    assert "resolve_agent_session_mode" not in source
    assert 'binding.get("session_mode")' in source


def test_redis_network_store_is_orm_free() -> None:
    source = REDIS_STORE_FILE.read_text(encoding="utf-8")
    tree = _parse(REDIS_STORE_FILE)
    imports = _import_modules(tree)
    assert not any(module.startswith("modules.network.infra.database") for module in imports)
    assert not any(module == "sqlalchemy" or module.startswith("sqlalchemy.") for module in imports)
    assert "NetworkExecutionModel" not in source
    assert "NetworkInvocationModel" not in source
