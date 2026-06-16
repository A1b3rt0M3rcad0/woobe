import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULES = ["agent", "billing", "core", "identity", "metering", "observability"]

EXPECTED_PREFIXES = {
    "agent": "/agent",
    "billing": "/billing",
    "core": "/core",
    "identity": "/identity",
    "metering": "/metering",
    "observability": "/observability",
}


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


class TestApiRoutesRegistered:
    def test_each_module_has_routes_file(self):
        for mod in MODULES:
            routes_path = PROJECT_ROOT / "src" / "modules" / mod / "presentation" / "routes.py"
            assert routes_path.exists(), f"{mod} missing routes.py"

    def test_each_module_routes_exports_router(self):
        for mod in MODULES:
            routes_path = PROJECT_ROOT / "src" / "modules" / mod / "presentation" / "routes.py"
            source = routes_path.read_text(encoding="utf-8")
            assert "router" in source, f"{mod} routes.py missing router variable"

    def test_main_py_imports_all_module_routes(self):
        main_path = PROJECT_ROOT / "src" / "main.py"
        source = main_path.read_text(encoding="utf-8")
        for mod in MODULES:
            assert f"modules.{mod}.presentation" in source or f"modules.{mod}.routes" in source, (
                f"main.py must import {mod} routes"
            )

    def test_main_py_includes_all_module_routers(self):
        main_path = PROJECT_ROOT / "src" / "main.py"
        source = main_path.read_text(encoding="utf-8")
        for mod in MODULES:
            assert f"{mod}_router" in source or f"include_router({mod}" in source or f"{mod}.routes" in source, (
                f"main.py must include {mod} router"
            )

    def test_each_module_init_exports_routes_function(self):
        for mod in MODULES:
            init_path = PROJECT_ROOT / "src" / "modules" / mod / "__init__.py"
            source = init_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            all_list = None
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "__all__":
                            all_list = node.value
            assert all_list is not None, f"{mod} __init__.py missing __all__"
            all_els = {el.value for el in all_list.elts} if isinstance(all_list, (ast.List, ast.Tuple)) else set()
            assert "routes" in all_els, f"{mod} __all__ missing 'routes'"

    def test_module_init_imports_routes(self):
        for mod in MODULES:
            init_path = PROJECT_ROOT / "src" / "modules" / mod / "__init__.py"
            source = init_path.read_text(encoding="utf-8")
            assert "presentation" in source and "routes" in source, \
                f"{mod} __init__.py must import from presentation.routes"

    def test_legacy_route_prefixes_preserved_in_agent(self):
        routes_path = PROJECT_ROOT / "src" / "modules" / "agent" / "presentation" / "routes.py"
        source = routes_path.read_text(encoding="utf-8")
        for legacy in ("/ai", "/knowledge", "/runtime"):
            assert legacy in source or legacy.replace("/", "") in source, (
                f"Agent routes must preserve legacy prefix {legacy}"
            )
