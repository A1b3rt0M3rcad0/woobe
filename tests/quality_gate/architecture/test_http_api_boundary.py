"""Repository-level contracts for the HTTP/API extraction."""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_ROOT = PROJECT_ROOT / "packages/woobe-core/src"
API_ROOT = PROJECT_ROOT / "packages/woobe-api/src"
WORKERS_ROOT = PROJECT_ROOT / "packages/woobe-workers/src"
BOUNDED_CONTEXTS = {
    "agent",
    "chat_surface",
    "core",
    "identity",
    "metering",
    "network",
    "observability",
}


def _literal_dynamic_import(node: ast.Call) -> str | None:
    if not node.args:
        return None
    target = node.args[0]
    if not isinstance(target, ast.Constant) or not isinstance(target.value, str):
        return None
    if isinstance(node.func, ast.Name) and node.func.id == "__import__":
        return target.value
    if (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "import_module"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "importlib"
    ):
        return target.value
    return None


def _import_from_targets(node: ast.ImportFrom) -> tuple[str, ...]:
    if not node.module:
        return ()
    targets = []
    for alias in node.names:
        if alias.name == "*":
            targets.append(node.module)
        else:
            targets.append(f"{node.module}.{alias.name}")
    return tuple(targets)


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.extend(_import_from_targets(node))
        elif isinstance(node, ast.Call):
            dynamic_import = _literal_dynamic_import(node)
            if dynamic_import is not None:
                imports.append(dynamic_import)
    return tuple(imports)


def test_import_inventory_resolves_import_from_targets(tmp_path: Path) -> None:
    source = tmp_path / "import_from.py"
    source.write_text(
        "from modules import agent\n"
        "from modules.agent import entrypoint\n"
        "from modules.agent.entrypoint import AskInput\n",
        encoding="utf-8",
    )

    imported = _imports(source)

    assert "modules.agent" in imported
    assert "modules.agent.entrypoint" in imported
    assert "modules.agent.entrypoint.AskInput" in imported


def test_import_inventory_detects_literal_dynamic_imports(tmp_path: Path) -> None:
    source = tmp_path / "dynamic_imports.py"
    source.write_text(
        "import importlib\n"
        'importlib.import_module("modules.agent.infra.database")\n'
        '__import__("modules.network.application.service")\n',
        encoding="utf-8",
    )

    imported = _imports(source)

    assert "modules.agent.infra.database" in imported
    assert "modules.network.application.service" in imported


def test_woobe_core_is_transport_framework_free() -> None:
    violations = []
    for path in CORE_ROOT.rglob("*.py"):
        for imported in _imports(path):
            if imported == "fastapi" or imported.startswith("fastapi."):
                violations.append((path, imported))
            if imported == "starlette" or imported.startswith("starlette."):
                violations.append((path, imported))
    assert not violations


def test_woobe_core_never_depends_on_api_host() -> None:
    violations = [
        (path, imported)
        for path in CORE_ROOT.rglob("*.py")
        for imported in _imports(path)
        if imported == "woobe_api" or imported.startswith("woobe_api.")
    ]
    assert not violations


def test_application_layers_never_depend_on_infrastructure() -> None:
    violations = []
    for context in sorted(BOUNDED_CONTEXTS):
        application_root = CORE_ROOT / f"modules/{context}/application"
        for path in application_root.rglob("*.py"):
            for imported in _imports(path):
                parts = imported.split(".")
                is_module_infra = (
                    len(parts) >= 3
                    and parts[0] == "modules"
                    and parts[2] == "infra"
                )
                if (
                    is_module_infra
                    or imported == "shared.infra"
                    or imported.startswith("shared.infra.")
                    or imported == "sqlalchemy"
                    or imported.startswith("sqlalchemy.")
                ):
                    violations.append((path, imported))
    assert not violations


def test_api_consumes_bounded_contexts_only_through_public_boundaries() -> None:
    violations = []
    for path in API_ROOT.rglob("*.py"):
        for imported in _imports(path):
            parts = imported.split(".")
            if len(parts) < 2 or parts[0] != "modules" or parts[1] not in BOUNDED_CONTEXTS:
                continue
            if len(parts) < 3 or parts[2] not in {"entrypoint", "background_boundary"}:
                violations.append((path, imported))
    assert not violations


def test_http_routers_do_not_wire_persistence() -> None:
    violations = []
    for path in (API_ROOT / "woobe_api/http").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for imported in _imports(path):
            if imported == "sqlalchemy" or imported.startswith("sqlalchemy."):
                violations.append((path, imported))
            if imported == "shared.composition_resources":
                violations.append((path, imported))
            if imported == "shared.infra.database" or imported.startswith(
                "shared.infra.database."
            ):
                violations.append((path, imported))
            parts = imported.split(".")
            if len(parts) >= 3 and parts[0] == "modules" and parts[2] == "infra":
                violations.append((path, imported))
        if ".state.session_factory" in source:
            violations.append((path, "request.app.state.session_factory"))
    assert not violations


def test_http_security_adapter_does_not_own_persistence_rules() -> None:
    security_root = API_ROOT / "woobe_api/security"
    violations = [
        (path, imported)
        for path in security_root.rglob("*.py")
        for imported in _imports(path)
        if imported == "sqlalchemy"
        or imported.startswith("sqlalchemy.")
        or imported == "shared.infra.database"
        or imported.startswith("shared.infra.database.")
        or imported == "shared.security.tenancy"
        or imported.startswith("shared.security.tenancy.")
    ]
    assert not violations


def test_security_authentication_contract_is_persistence_neutral() -> None:
    contract = CORE_ROOT / "shared/security/authentication.py"
    forbidden = ("fastapi", "starlette", "sqlalchemy", "shared.infra")
    violations = [
        imported
        for imported in _imports(contract)
        if any(
            imported == prefix or imported.startswith(f"{prefix}.")
            for prefix in forbidden
        )
    ]
    assert not violations
    assert (
        CORE_ROOT / "shared/infra/security/authentication.py"
    ).is_file(), "SQL authentication must be owned by shared infrastructure"


def test_workers_consume_only_public_module_boundaries() -> None:
    violations = []
    for path in WORKERS_ROOT.rglob("*.py"):
        for imported in _imports(path):
            parts = imported.split(".")
            if len(parts) < 2 or parts[0] != "modules" or parts[1] not in BOUNDED_CONTEXTS:
                continue
            if len(parts) < 3 or parts[2] not in {"entrypoint", "background_boundary"}:
                violations.append((path, imported))
    assert not violations


def test_each_http_bounded_context_has_a_public_entrypoint() -> None:
    missing = [
        context
        for context in sorted(BOUNDED_CONTEXTS)
        if not (CORE_ROOT / f"modules/{context}/entrypoint.py").is_file()
    ]
    assert not missing


def test_entrypoints_reach_internals_only_through_composition() -> None:
    violations = []
    for context in sorted(BOUNDED_CONTEXTS):
        path = CORE_ROOT / f"modules/{context}/entrypoint.py"
        expected_prefix = f"modules.{context}.composition"
        for imported in _imports(path):
            if not (
                imported == expected_prefix
                or imported.startswith(f"{expected_prefix}.")
            ):
                violations.append((path, imported))
    assert not violations


def test_legacy_http_and_composer_locations_are_absent() -> None:
    violations = []
    for context in sorted(BOUNDED_CONTEXTS):
        module = CORE_ROOT / f"modules/{context}"
        for relative in ("presentation/http", "application/composers"):
            if any((module / relative).rglob("*.py")):
                violations.append(f"{context}/{relative}")
    assert not violations


def test_shared_http_transport_package_is_absent_from_core() -> None:
    assert not any((CORE_ROOT / "shared/presentation/http").rglob("*.py"))


def test_chat_surface_has_no_loose_root_services() -> None:
    module_root = CORE_ROOT / "modules/chat_surface"
    unexpected = [
        path.name
        for path in module_root.glob("*.py")
        if path.name not in {"__init__.py", "background_boundary.py", "entrypoint.py"}
    ]
    assert not unexpected
