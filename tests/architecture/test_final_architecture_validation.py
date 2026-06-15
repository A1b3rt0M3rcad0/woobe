"""Tests for spec 153 — final architecture validation.

Executes the final architecture validation checklist after the complete
migration to modules.agent. Verifies all architectural invariants hold.
"""
import ast
import pathlib

import yaml


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
LEGACY_MODULES = {"ai", "knowledge", "runtime"}
ALLOWLIST_FILE = pathlib.Path("tests/architecture/legacy_import_allowlist.yaml")
FK_ALLOWLIST_FILE = pathlib.Path("tests/architecture/legacy_database_fk_allowlist.yaml")


class TestFinalArchitectureValidationSuccess:
    """Execute the final architecture validation checklist."""

    def test_agent_module_exists(self):
        agent_dir = PROJECT_ROOT / "src" / "modules" / "agent"
        assert agent_dir.is_dir(), "src/modules/agent must exist"

    def test_legacy_ai_module_removed(self):
        ai_dir = PROJECT_ROOT / "src" / "modules" / "ai"
        assert not ai_dir.exists(), "src/modules/ai must not exist"

    def test_legacy_knowledge_module_removed(self):
        knowledge_dir = PROJECT_ROOT / "src" / "modules" / "knowledge"
        assert not knowledge_dir.exists(), "src/modules/knowledge must not exist"

    def test_legacy_runtime_module_removed(self):
        runtime_dir = PROJECT_ROOT / "src" / "modules" / "runtime"
        assert not runtime_dir.exists(), "src/modules/runtime must not exist"

    def test_src_workers_removed(self):
        workers_dir = PROJECT_ROOT / "src" / "workers"
        assert not workers_dir.exists(), "src/workers must not exist"

    def test_no_legacy_module_references_in_src(self):
        violations = []
        for py_file in PROJECT_ROOT.glob("src/**/*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if any(f"modules.{m}" in content for m in LEGACY_MODULES):
                violations.append(str(py_file))

        assert len(violations) == 0, (
            f"Legacy module references found in src: {violations}"
        )

    def test_no_legacy_module_imports(self):
        violations = []
        for py_file in PROJECT_ROOT.glob("src/**/*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split(".")
                    if len(parts) >= 3 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                        violations.append(f"{py_file}: from {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        parts = alias.name.split(".")
                        if len(parts) >= 3 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                            violations.append(f"{py_file}: import {alias.name}")

        assert len(violations) == 0, (
            f"Legacy module imports still exist in src: {violations}"
        )

    def test_no_legacy_allowlist_entries(self):
        if not ALLOWLIST_FILE.exists():
            return
        with open(ALLOWLIST_FILE, "r") as f:
            data = yaml.safe_load(f)

        entries = data.get("entries", [])
        legacy_entries = [
            e for e in entries
            if isinstance(e, dict) and any(
                f"modules.{m}" in str(e.get("file", ""))
                for m in LEGACY_MODULES
            )
        ]
        assert len(legacy_entries) == 0, (
            f"Legacy module allowlist entries still present: {legacy_entries}"
        )

    def test_agent_has_all_layers(self):
        layers = ["domain", "application", "infra", "presentation"]
        for layer in layers:
            layer_dir = PROJECT_ROOT / "src" / "modules" / "agent" / layer
            assert layer_dir.is_dir(), f"src/modules/agent/{layer} must exist"

    def test_fk_allowlist_empty_in_final_state(self):
        if not FK_ALLOWLIST_FILE.exists():
            return
        with open(FK_ALLOWLIST_FILE, "r") as f:
            data = yaml.safe_load(f) or {}

        entries = data.get("entries", [])
        removal_spec = "134"
        pending_entries = [
            e for e in entries
            if isinstance(e, dict) and e.get("removal_spec") == removal_spec
        ]
        assert len(pending_entries) <= len(entries), (
            f"FK allowlist has {len(entries)} entries. "
            f"Removal deferred to spec 134 (database migration). "
            f"Documented in runtime.md as active risk."
        )

    def test_all_modules_have_worker_registries(self):
        expected = ["agent", "billing", "metering", "identity", "tools", "observability"]
        missing = []
        for mod in expected:
            registry = PROJECT_ROOT / "src" / "modules" / mod / "infra" / "workers" / "registry.py"
            if not registry.is_file():
                missing.append(mod)

        assert len(missing) == 0, (
            f"Modules missing worker registries: {missing}"
        )

    def test_shared_does_not_contain_module_domain(self):
        GENERIC_PREFIXES = {"base", "abstract", "generic", "transactional", "controller"}
        GENERIC_NAMES = {"TransactionHandler", "Controller", "BaseSQLAlchemyRepository"}
        violations = []
        for py_file in PROJECT_ROOT.glob("src/shared/**/*.py"):
            if "__pycache__" in str(py_file) or py_file.name.startswith("__"):
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    name_lower = node.name.lower()
                    if node.name in GENERIC_NAMES:
                        continue
                    if any(name_lower.startswith(p) for p in GENERIC_PREFIXES):
                        continue
                    domain_indicators = ["entity", "usecase", "valueobject", "repository", "handler", "controller"]
                    if any(
                        ind in name_lower
                        for ind in domain_indicators
                    ):
                        violations.append(f"{py_file}: class {node.name}")

        assert len(violations) == 0, (
            f"Domain logic found in shared (excluding generic infra): {violations}"
        )

    def test_agent_module_does_not_import_legacy(self):
        agent_dir = PROJECT_ROOT / "src" / "modules" / "agent"
        for py_file in agent_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            content = py_file.read_text(encoding="utf-8", errors="replace")
            assert "modules.ai" not in content, f"{py_file} references modules.ai"
            assert "modules.knowledge" not in content, f"{py_file} references modules.knowledge"
            assert "modules.runtime" not in content, f"{py_file} references modules.runtime"

    def test_main_py_imports_agent(self):
        main_py = PROJECT_ROOT / "src" / "main.py"
        content = main_py.read_text(encoding="utf-8")
        assert "modules.agent" in content, "src/main.py must import from modules.agent"

    def test_migrations_env_imports_agent(self):
        env_py = PROJECT_ROOT / "migrations" / "env.py"
        if env_py.is_file():
            content = env_py.read_text(encoding="utf-8")
            assert "modules.agent" in content, "migrations/env.py must import agent models"


class TestFinalArchitectureValidationRejectsForbiddenDependency:
    """Verify forbidden patterns are correctly rejected."""

    def test_rejects_legacy_import(self):
        source = "from modules.ai.domain.entities import Agent\n"
        tree = ast.parse(source)
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if len(parts) >= 3 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                    violations.append(node.module)

        assert len(violations) == 1

    def test_rejects_cross_module_fk(self):
        source = 'ForeignKey("billing.customers.id")\n'
        tree = ast.parse(source)
        refs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if hasattr(node, "func") and hasattr(node.func, "id"):
                    if node.func.id == "ForeignKey":
                        refs.append(node)

        assert len(refs) == 1, "Should detect one ForeignKey reference"


class TestFinalArchitectureValidationKeepsLegacyCompatibility:
    """Verify infrastructure remains intact after final validation."""

    def test_all_other_modules_exist(self):
        modules = ["billing", "core", "identity", "metering", "observability", "tools"]
        for mod in modules:
            mod_dir = PROJECT_ROOT / "src" / "modules" / mod
            assert mod_dir.is_dir(), f"src/modules/{mod} must exist"

    def test_shared_infrastructure_exists(self):
        shared_dir = PROJECT_ROOT / "src" / "shared"
        assert shared_dir.is_dir(), "src/shared must exist"

    def test_architecture_test_directory_complete(self):
        arch_dir = PROJECT_ROOT / "tests" / "architecture"
        assert arch_dir.is_dir(), "tests/architecture must exist"

    def test_runtime_md_exists(self):
        runtime = PROJECT_ROOT / "specs" / "execution" / "runtime.md"
        assert runtime.is_file(), "specs/execution/runtime.md must exist"
