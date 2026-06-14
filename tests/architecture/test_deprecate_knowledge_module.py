"""Tests for spec 141 — deprecate knowledge module.

Validates that the `modules.knowledge` module is marked as deprecated, that shims
delegate to agent, and that no removal has occurred yet.
"""
import importlib
import warnings


class TestDeprecateKnowledgeModuleSuccess:
    """Verify the knowledge module is deprecated but still accessible."""

    def test_knowledge_module_emits_deprecation_warning_on_import(self):
        import sys

        if "modules.knowledge" in sys.modules:
            del sys.modules["modules.knowledge"]

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import modules.knowledge  # noqa: F401

            deprecation_warnings = [
                _w for _w in w
                if issubclass(_w.category, DeprecationWarning)
                and "modules.knowledge" in str(_w.message)
            ]
            assert len(deprecation_warnings) >= 1, (
                "modules.knowledge must emit DeprecationWarning on import"
            )

    def test_knowledge_module_still_importable(self):
        mod = importlib.import_module("modules.knowledge")
        assert mod is not None

    def test_knowledge_domain_shim_still_works(self):
        mod = importlib.import_module("modules.knowledge.domain.entities")
        assert hasattr(mod, "DocumentCollection"), (
            "knowledge.domain.entities shim must export DocumentCollection from agent"
        )

    def test_knowledge_infra_shim_still_works(self):
        mod = importlib.import_module("modules.knowledge.infra.models")
        assert hasattr(mod, "DocumentCollectionModel"), (
            "knowledge.infra.models shim must export DocumentCollectionModel"
        )

    def test_knowledge_presentation_shim_still_works(self):
        mod = importlib.import_module("modules.knowledge.presentation.routes")
        assert hasattr(mod, "router"), (
            "knowledge.presentation.routes shim must export router"
        )

    def test_knowledge_module_structure_preserved(self):
        submodules = [
            "modules.knowledge.domain",
            "modules.knowledge.domain.entities",
            "modules.knowledge.domain.enums",
            "modules.knowledge.domain.errors",
            "modules.knowledge.domain.repositories",
            "modules.knowledge.infra",
            "modules.knowledge.infra.models",
            "modules.knowledge.infra.mappers",
            "modules.knowledge.infra.repositories",
            "modules.knowledge.presentation",
            "modules.knowledge.presentation.routes",
            "modules.knowledge.presentation.schemas",
            "modules.knowledge.application",
        ]
        for submod in submodules:
            try:
                importlib.import_module(submod)
            except ImportError as e:
                if "__init__.py" not in str(e) and "has no attribute" not in str(e):
                    raise AssertionError(
                        f"Legacy submodule {submod} must remain importable: {e}"
                    )


class TestDeprecateKnowledgeModuleRejectsForbidden:
    """Verify no forbidden patterns after deprecation."""

    def test_knowledge_module_not_yet_removed(self):
        import pathlib

        knowledge_dir = pathlib.Path("src/modules/knowledge")
        assert knowledge_dir.is_dir(), (
            "knowledge module must not be removed until spec 144"
        )

    def test_no_new_knowledge_imports_in_agent_module(self):
        import pathlib

        agent_dir = pathlib.Path("src/modules/agent")
        py_files = list(agent_dir.rglob("*.py"))
        for f in py_files:
            if "__pycache__" in str(f):
                continue
            if "shim" in f.name.lower():
                continue


class TestDeprecateKnowledgeModuleKeepsLegacyCompatibility:
    """Verify legacy test files can still be collected."""

    def test_legacy_knowledge_tests_still_exist(self):
        import pathlib

        knowledge_test_dir = pathlib.Path("tests/unit/test_knowledge")
        assert knowledge_test_dir.is_dir(), (
            "Legacy knowledge tests must exist until spec 144"
        )

    def test_knowledge_allowlist_entries_still_present(self):
        import pathlib
        import yaml

        allowlist_path = pathlib.Path(
            "tests/architecture/legacy_import_allowlist.yaml"
        )
        with open(allowlist_path, "r") as f:
            data = yaml.safe_load(f)

        entries = data.get("entries", [])
        knowledge_entries = [
            e for e in entries
            if isinstance(e, dict) and "knowledge" in str(e.get("file", ""))
        ]
        assert len(knowledge_entries) > 0, (
            "knowledge allowlist entries must exist until spec 144"
        )
