"""Tests for spec 154 — final migration report.

Validates that the final migration report exists, has required sections,
and accurately reflects the current repository state.
"""
import pathlib


REPORT_PATH = pathlib.Path("specs/execution/final-report.md")
RUNTIME_PATH = pathlib.Path("specs/execution/runtime.md")


class TestFinalMigrationReportSuccess:
    """Verify the final migration report is complete and accurate."""

    def test_final_report_exists(self):
        assert REPORT_PATH.is_file(), (
            "specs/execution/final-report.md must exist"
        )

    def test_final_report_is_not_empty(self):
        content = REPORT_PATH.read_text(encoding="utf-8")
        assert len(content.strip()) > 100, (
            "Final report must have substantive content"
        )

    def test_final_report_has_required_sections(self):
        content = REPORT_PATH.read_text(encoding="utf-8")
        required_sections = [
            "Specs executadas",
            "Estado da migração",
            "Validações executadas",
            "Riscos resolvidos",
            "Riscos remanescentes",
            "Próximos passos",
        ]
        for section in required_sections:
            assert section in content, (
                f"Final report missing required section: '{section}'"
            )

    def test_final_report_references_commit_info(self):
        content = REPORT_PATH.read_text(encoding="utf-8")
        assert "project-rai-playground_specs-refactory" in content, (
            "Final report must reference the branch name"
        )
        assert "spec 153" in content or "spec 154" in content, (
            "Final report must reference recent commits"
        )

    def test_final_report_lists_legacy_modules_removed(self):
        content = REPORT_PATH.read_text(encoding="utf-8")
        assert "src/modules/ai/" in content or "removido" in content, (
            "Final report must document ai module removal"
        )
        assert "src/modules/knowledge/" in content or "removido" in content, (
            "Final report must document knowledge module removal"
        )
        assert "src/modules/runtime/" in content or "removido" in content, (
            "Final report must document runtime module removal"
        )

    def test_runtime_md_exists_and_updated(self):
        assert RUNTIME_PATH.is_file(), (
            "specs/execution/runtime.md must exist"
        )

    def test_migration_target_agent_exists(self):
        agent_dir = pathlib.Path("src/modules/agent")
        assert agent_dir.is_dir(), "src/modules/agent must be the target module"

    def test_legacy_modules_directories_removed(self):
        for legacy in ("ai", "knowledge", "runtime"):
            legacy_dir = pathlib.Path(f"src/modules/{legacy}")
            assert not legacy_dir.exists(), (
                f"Legacy module src/modules/{legacy} must not exist"
            )


class TestFinalMigrationReportRejectsForbiddenDependency:
    """Verify forbidden patterns are still rejected in final state."""

    def test_no_legacy_imports_anywhere(self):
        import ast

        violations = []
        for py_file in pathlib.Path("src").rglob("*.py"):
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
                    if len(parts) >= 3 and parts[0] == "modules" and parts[1] in {"ai", "knowledge", "runtime"}:
                        violations.append(f"{py_file}: from {node.module}")

        assert len(violations) == 0, (
            f"Legacy imports detected in final state: {violations}"
        )

    def test_no_src_workers_directory(self):
        workers_dir = pathlib.Path("src/workers")
        assert not workers_dir.exists(), "src/workers must be removed"


class TestFinalMigrationReportKeepsLegacyCompatibility:
    """Verify infrastructure is preserved in final state."""

    def test_shared_workers_infrastructure_exists(self):
        runner = pathlib.Path("src/shared/workers/runner.py")
        assert runner.is_file(), "shared.workers.runner must exist"

    def test_all_module_worker_registries_exist(self):
        modules = ["agent", "billing", "metering", "identity", "tools", "observability"]
        for mod in modules:
            registry = pathlib.Path(f"src/modules/{mod}/infra/workers/registry.py")
            assert registry.is_file(), f"{mod} worker registry must exist"

    def test_main_py_exists(self):
        main_py = pathlib.Path("src/main.py")
        assert main_py.is_file(), "src/main.py must exist"

    def test_migrations_env_exists(self):
        env_py = pathlib.Path("migrations/env.py")
        assert env_py.is_file(), "migrations/env.py must exist"
