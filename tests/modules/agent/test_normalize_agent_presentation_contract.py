from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PRESENTATION_DIR = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "agent" / "presentation"
CONTROLLERS_DIR = PRESENTATION_DIR / "controllers"
ROUTES_FILE = PRESENTATION_DIR / "routes.py"
SCHEMAS_FILE = PRESENTATION_DIR / "schemas.py"
MAPPERS_FILE = PRESENTATION_DIR / "mappers.py"

EXPECTED_PRESENTATION_FILES = [
    "__init__.py",
    "routes.py",
    "schemas.py",
    "mappers.py",
]

LEGACY_PREFIXES = ["/ai", "/knowledge", "/runtime"]

CANONICAL_PREFIX = "/agent"


class TestNormalizeAgentPresentationContract:
    def test_presentation_directory_exists(self):
        assert PRESENTATION_DIR.is_dir()

    def test_controllers_directory_exists(self):
        assert CONTROLLERS_DIR.is_dir()

    def test_all_required_presentation_files_exist(self):
        for name in EXPECTED_PRESENTATION_FILES:
            file_path = PRESENTATION_DIR / name
            assert file_path.is_file(), f"Missing presentation file: {name}"

    def test_routes_exists_and_is_populated(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert "APIRouter" in content, "routes.py must use APIRouter"
        assert len(content) > 10000, "routes.py must be substantial"

    def test_routes_preserves_all_legacy_prefixes(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        for prefix in LEGACY_PREFIXES:
            assert f'prefix="{prefix}"' in content or f"prefix='{prefix}'" in content, \
                f"routes.py missing legacy prefix: {prefix}"

    def test_routes_has_canonical_agent_router(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert f'prefix="{CANONICAL_PREFIX}"' in content or f"prefix='{CANONICAL_PREFIX}'" in content

    def test_agent_router_includes_all_legacy_routers(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert "agent_router.include_router(router)" in content
        assert "agent_router.include_router(knowledge_router)" in content
        assert "agent_router.include_router(runtime_router)" in content

    def test_schemas_exists_and_is_populated(self):
        content = SCHEMAS_FILE.read_text(encoding="utf-8")
        assert len(content) > 10000, "schemas.py must be substantial"

    def test_mappers_exists_and_is_populated(self):
        content = MAPPERS_FILE.read_text(encoding="utf-8")
        assert len(content) > 10000, "mappers.py must be substantial"

    def test_controllers_have_enough_files(self):
        py_files = [f for f in CONTROLLERS_DIR.iterdir() if f.suffix == ".py" and not f.name.startswith("__")]
        assert len(py_files) >= 30, f"Expected 30+ controller files, found {len(py_files)}"

    def test_routes_reference_all_composers(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        composer_count = content.count("_composer(")
        assert composer_count >= 40, f"Expected 40+ composer references in routes, found {composer_count}"

    def test_no_legacy_imports_in_presentation(self):
        for py_file in PRESENTATION_DIR.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            content = py_file.read_text(encoding="utf-8")
            for mod in ("modules.ai", "modules.knowledge", "modules.runtime"):
                assert mod not in content, f"{py_file.name} references {mod}"
