from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_MODULES = PROJECT_ROOT / "src" / "modules"

ALL_MODULES = {"agent", "identity", "core", "billing", "metering", "observability", "tools"}

MANDATORY_DOMAIN_FILES = {
    "entities.py",
    "enums.py",
    "errors.py",
    "repositories.py",
}

CONDITIONAL_DOMAIN_FILES = {
    "events.py",
    "services.py",
    "value_objects.py",
}

CANONICAL_PRESENTATION_FILES = {
    "mappers.py",
    "routes.py",
    "schemas.py",
}


def _get_module_dirs(module: str) -> set[str]:
    mod_path = SRC_MODULES / module
    if not mod_path.is_dir():
        return set()
    return {
        p.relative_to(mod_path).as_posix()
        for p in mod_path.rglob("*")
        if p.is_dir() and p.name != "__pycache__"
    }


def _get_module_files(module: str, subdir: str) -> set[str]:
    dir_path = SRC_MODULES / module / subdir
    if not dir_path.is_dir():
        return set()
    return {
        p.name for p in dir_path.iterdir()
        if p.is_file() and p.suffix == ".py"
    }


class TestModuleStructure:
    def test_persisted_modules_follow_canonical_structure(self):
        for module in sorted(ALL_MODULES):
            mod_path = SRC_MODULES / module
            assert mod_path.is_dir(), f"Module {module} must exist"

            dirs = _get_module_dirs(module)

            mandatory_dirs = {"application", "domain", "infra", "presentation"}
            for d in mandatory_dirs:
                assert d in dirs, (
                    f"{module} must have mandatory directory '{d}'"
                )

            assert "application/composers" in dirs, (
                f"{module} must have application/composers/"
            )

            assert "domain" in dirs, (
                f"{module} must have domain/"
            )

            domain_files = _get_module_files(module, "domain")
            for f in MANDATORY_DOMAIN_FILES:
                assert f in domain_files, (
                    f"{module}/domain/{f} must exist"
                )

            assert "presentation" in dirs, (
                f"{module} must have presentation/"
            )

            assert "presentation/controllers" in dirs, (
                f"{module} must have presentation/controllers/"
            )

            pres_files = _get_module_files(module, "presentation")
            for f in CANONICAL_PRESENTATION_FILES:
                if f == "mappers.py" and module != "agent" and module != "core":
                    continue
                assert f in pres_files, (
                    f"{module}/presentation/{f} must exist"
                )

    def test_legacy_service_dir_noted_for_non_agent_modules(self):
        legacy_modules = {"identity", "core", "billing", "metering", "observability", "tools"}
        for module in sorted(legacy_modules):
            dirs = _get_module_dirs(module)
            has_service = "service" in dirs
            assert has_service, (
                f"{module} should have service/ (legacy) or application/use_cases/"
            )

    def test_agent_has_canonical_infra_structure(self):
        agent_dirs = _get_module_dirs("agent")

        assert "infra/database" in agent_dirs, (
            "agent must have infra/database/"
        )
        assert "infra/messaging" in agent_dirs, (
            "agent must have infra/messaging/"
        )
        assert "infra/workers" in agent_dirs, (
            "agent must have infra/workers/"
        )

        infra_db_files = _get_module_files("agent", "infra/database")
        for f in ("mappers.py", "models.py", "repositories.py", "unit_of_work.py"):
            assert f in infra_db_files, (
                f"agent/infra/database/{f} must exist"
            )

        assert "infra/llm" in agent_dirs, (
            "agent must have infra/llm/ (module-specific capability)"
        )

    def test_non_agent_modules_have_flat_infra(self):
        legacy_modules = {"identity", "core", "billing", "metering", "observability", "tools"}
        for module in sorted(legacy_modules):
            mod_path = SRC_MODULES / module / "infra"
            infra_files = {
                p.name for p in mod_path.iterdir()
                if p.is_file() and p.suffix == ".py"
            }

            for f in ("mappers.py", "models.py", "repositories.py"):
                assert f in infra_files, (
                    f"{module}/infra/{f} must exist"
                )
