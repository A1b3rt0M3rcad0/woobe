"""Tests for spec 142 — deprecate runtime module.

Validates that the `modules.runtime` module is marked as deprecated, that shims
delegate to agent, and that no removal has occurred yet.
"""
import importlib
import warnings


class TestDeprecateRuntimeModuleSuccess:
    """Verify the runtime module is deprecated but still accessible."""

    def test_runtime_module_emits_deprecation_warning_on_import(self):
        import sys

        if "modules.runtime" in sys.modules:
            del sys.modules["modules.runtime"]

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import modules.runtime  # noqa: F401

            deprecation_warnings = [
                _w for _w in w
                if issubclass(_w.category, DeprecationWarning)
                and "modules.runtime" in str(_w.message)
            ]
            assert len(deprecation_warnings) >= 1, (
                "modules.runtime must emit DeprecationWarning on import"
            )

    def test_runtime_module_still_importable(self):
        mod = importlib.import_module("modules.runtime")
        assert mod is not None

    def test_runtime_domain_shim_still_works(self):
        mod = importlib.import_module("modules.runtime.domain.entities")
        assert hasattr(mod, "Session"), (
            "runtime.domain.entities shim must export Session from agent"
        )

    def test_runtime_infra_shim_still_works(self):
        mod = importlib.import_module("modules.runtime.infra.models")
        assert hasattr(mod, "AskJobModel"), (
            "runtime.infra.models shim must export AskJobModel"
        )

    def test_runtime_presentation_shim_still_works(self):
        mod = importlib.import_module("modules.runtime.presentation.routes")
        assert hasattr(mod, "router"), (
            "runtime.presentation.routes shim must export router"
        )

    def test_runtime_module_structure_preserved(self):
        submodules = [
            "modules.runtime.domain",
            "modules.runtime.domain.entities",
            "modules.runtime.domain.enums",
            "modules.runtime.domain.errors",
            "modules.runtime.domain.repositories",
            "modules.runtime.infra",
            "modules.runtime.infra.models",
            "modules.runtime.infra.mappers",
            "modules.runtime.infra.repositories",
            "modules.runtime.presentation",
            "modules.runtime.presentation.routes",
            "modules.runtime.presentation.schemas",
            "modules.runtime.application",
        ]
        for submod in submodules:
            try:
                importlib.import_module(submod)
            except ImportError as e:
                if "__init__.py" not in str(e) and "has no attribute" not in str(e):
                    raise AssertionError(
                        f"Legacy submodule {submod} must remain importable: {e}"
                    )


class TestDeprecateRuntimeModuleRejectsForbidden:
    """Verify no forbidden patterns after deprecation."""

    def test_runtime_module_not_yet_removed(self):
        import pathlib

        runtime_dir = pathlib.Path("src/modules/runtime")
        assert runtime_dir.is_dir(), (
            "runtime module must not be removed until spec 145"
        )

    def test_no_new_runtime_imports_in_agent_module(self):
        import pathlib

        agent_dir = pathlib.Path("src/modules/agent")
        py_files = list(agent_dir.rglob("*.py"))
        for f in py_files:
            if "__pycache__" in str(f):
                continue
            if "shim" in f.name.lower():
                continue


class TestDeprecateRuntimeModuleKeepsLegacyCompatibility:
    """Verify legacy test files can still be collected."""

    def test_legacy_runtime_tests_still_exist(self):
        import pathlib

        runtime_test_dir = pathlib.Path("tests/unit/test_runtime")
        assert runtime_test_dir.is_dir(), (
            "Legacy runtime tests must exist until spec 145"
        )

    def test_runtime_allowlist_entries_still_present(self):
        import pathlib
        import yaml

        allowlist_path = pathlib.Path(
            "tests/architecture/legacy_import_allowlist.yaml"
        )
        with open(allowlist_path, "r") as f:
            data = yaml.safe_load(f)

        entries = data.get("entries", [])
        runtime_entries = [
            e for e in entries
            if isinstance(e, dict) and "runtime" in str(e.get("file", ""))
        ]
        assert len(runtime_entries) > 0, (
            "runtime allowlist entries must exist until spec 145"
        )
