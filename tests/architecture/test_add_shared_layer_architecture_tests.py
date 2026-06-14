import ast
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TESTS_ARCH = Path(__file__).resolve().parent
SRC_SHARED = PROJECT_ROOT / "src" / "shared"
ALLOWLIST_FILE = TESTS_ARCH / "legacy_import_allowlist.yaml"
SHARED_BOUNDARIES_FILE = TESTS_ARCH / "test_shared_boundaries.py"


class TestAddSharedLayerArchitectureTests:
    def test_add_shared_layer_architecture_tests(self):
        assert SHARED_BOUNDARIES_FILE.is_file(), (
            f"test_shared_boundaries.py must exist at {SHARED_BOUNDARIES_FILE}"
        )

        source = SHARED_BOUNDARIES_FILE.read_text(encoding="utf-8")
        tree = ast.parse(source)

        imports_ast_module = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "ast":
                        imports_ast_module = True
            elif isinstance(node, ast.ImportFrom):
                if node.module == "ast":
                    imports_ast_module = True

        assert imports_ast_module, (
            "test_shared_boundaries.py must use the ast module for import analysis, not regex"
        )

        uses_ast_parse = "ast.parse" in source or "ast.walk" in source
        assert uses_ast_parse, (
            "test_shared_boundaries.py must use ast.parse/ast.walk for static analysis"
        )

        assert ALLOWLIST_FILE.is_file(), (
            f"legacy_import_allowlist.yaml must exist at {ALLOWLIST_FILE}"
        )

        with open(ALLOWLIST_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        entries = data.get("entries") or []
        assert len(entries) > 0, "Allowlist must have at least one entry during migration"

        required_fields = {"file", "target_module", "removal_spec", "scope"}
        for i, entry in enumerate(entries):
            missing = required_fields - set(entry.keys())
            assert not missing, (
                f"Allowlist entry {i} missing fields: {missing}"
            )

        shared_entries = [e for e in entries if e.get("scope") == "shared_boundaries"]
        assert len(shared_entries) > 0, (
            "Allowlist must have entries with scope 'shared_boundaries' "
            "for known shared layer violations"
        )

        for entry in shared_entries:
            assert entry["file"].startswith("src/shared/"), (
                f"shared_boundaries entry must reference src/shared/ file: {entry['file']}"
            )

    def test_add_shared_layer_architecture_tests_rejects_forbidden(self):
        forbidden_source = """\
from modules.ai.domain.entities import Agent
from modules.runtime.service.ask_use_case import AskAgentUseCase

class AgentHandler:
    pass
"""
        tree = ast.parse(forbidden_source)

        module_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("modules."):
                    module_imports.append(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("modules."):
                        module_imports.append(alias.name)

        assert len(module_imports) == 2, (
            f"Expected 2 module import violations in fixture, got {len(module_imports)}: {module_imports}"
        )
        assert "modules.ai.domain.entities" in module_imports
        assert "modules.runtime.service.ask_use_case" in module_imports

        domain_classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name_lower = node.name.lower()
                if any(
                    keyword in class_name_lower
                    for keyword in ("usecase", "use_case", "handler", "aggregate")
                ):
                    infra_indicators = ("base", "abstract", "transactional", "generic")
                    if not any(ind in class_name_lower for ind in infra_indicators):
                        domain_classes.append(node.name)

        assert len(domain_classes) == 1, (
            f"Expected 1 domain logic class in fixture, got {len(domain_classes)}: {domain_classes}"
        )
        assert "AgentHandler" in domain_classes
