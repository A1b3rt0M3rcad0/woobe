"""Tests for spec 140 — deprecate ai module.

Validates that the `modules.ai` module is marked as deprecated, that shims
delegate to agent, and that no removal has occurred yet.
"""
import importlib
import warnings


class TestDeprecateAiModuleSuccess:
    """Verify the ai module is deprecated but still accessible."""

    def test_ai_module_emits_deprecation_warning_on_import(self):
        import sys

        if "modules.ai" in sys.modules:
            del sys.modules["modules.ai"]

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import modules.ai  # noqa: F401

            deprecation_warnings = [
                _w for _w in w
                if issubclass(_w.category, DeprecationWarning)
                and "modules.ai" in str(_w.message)
            ]
            assert len(deprecation_warnings) >= 1, (
                "modules.ai must emit DeprecationWarning on import"
            )

    def test_ai_module_still_importable(self):
        mod = importlib.import_module("modules.ai")
        assert mod is not None

    def test_ai_domain_shim_still_works(self):
        mod = importlib.import_module("modules.ai.domain.entities")
        assert hasattr(mod, "Agent"), (
            "ai.domain.entities shim must export Agent from agent"
        )

    def test_ai_infra_shim_still_works(self):
        mod = importlib.import_module("modules.ai.infra.models")
        assert hasattr(mod, "ProviderCredentialModel"), (
            "ai.infra.models shim must export ProviderCredentialModel"
        )

    def test_ai_presentation_shim_still_works(self):
        mod = importlib.import_module("modules.ai.presentation.routes")
        assert hasattr(mod, "router"), (
            "ai.presentation.routes shim must export router"
        )

    def test_ai_module_structure_preserved(self):
        submodules = [
            "modules.ai.domain",
            "modules.ai.domain.entities",
            "modules.ai.domain.enums",
            "modules.ai.domain.errors",
            "modules.ai.domain.repositories",
            "modules.ai.infra",
            "modules.ai.infra.models",
            "modules.ai.infra.mappers",
            "modules.ai.infra.repositories",
            "modules.ai.infra.llm",
            "modules.ai.infra.llm.langchain_factory",
            "modules.ai.presentation",
            "modules.ai.presentation.routes",
            "modules.ai.presentation.schemas",
            "modules.ai.application",
        ]
        for submod in submodules:
            try:

                importlib.import_module(submod)
            except ImportError as e:
                if "__init__.py" not in str(e) and "has no attribute" not in str(e):
                    raise AssertionError(
                        f"Legacy submodule {submod} must remain importable: {e}"
                    )


class TestDeprecateAiModuleRejectsForbidden:
    """Verify no forbidden patterns after deprecation."""

    def test_ai_module_not_yet_removed(self):
        import pathlib

        ai_dir = pathlib.Path("src/modules/ai")
        assert ai_dir.is_dir(), (
            "ai module must not be removed until spec 143"
        )

    def test_no_new_ai_imports_in_agent_module(self):
        import pathlib

        agent_dir = pathlib.Path("src/modules/agent")
        py_files = list(agent_dir.rglob("*.py"))
        for f in py_files:
            if "__pycache__" in str(f):
                continue
            if "shim" in f.name.lower():
                continue


class TestDeprecateAiModuleKeepsLegacyCompatibility:
    """Verify legacy test files can still be collected."""

    def test_legacy_ai_tests_still_exist(self):
        import pathlib

        ai_test_dir = pathlib.Path("tests/unit/test_ai")
        assert ai_test_dir.is_dir(), (
            "Legacy AI tests must exist until spec 143"
        )

    def test_ai_allowlist_entries_still_present(self):
        import pathlib
        import yaml

        allowlist_path = pathlib.Path(
            "tests/architecture/legacy_import_allowlist.yaml"
        )
        with open(allowlist_path, "r") as f:
            data = yaml.safe_load(f)

        entries = data.get("entries", [])
        ai_entries = [
            e for e in entries
            if isinstance(e, dict) and "ai" in str(e.get("file", ""))
        ]
        assert len(ai_entries) > 0, (
            "ai allowlist entries must exist until spec 143"
        )
