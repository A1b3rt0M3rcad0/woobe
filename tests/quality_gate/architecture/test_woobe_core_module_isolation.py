from pathlib import Path
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[3]
POLICIES_ROOT = (
    PROJECT_ROOT
    / "tooling"
    / "quality-gate"
    / "src"
    / "quality_gate"
    / "architecture"
    / "policies"
)
WOOBE_CORE_MODULES_ROOT = "packages/woobe-core/src/modules/"


def test_woobe_core_module_policies_forbid_cross_module_imports() -> None:
    relaxed: list[str] = []

    for policy_file in sorted(POLICIES_ROOT.glob("*.toml")):
        with policy_file.open("rb") as handle:
            policy = tomllib.load(handle)

        module = policy.get("module") or {}
        module_root = str(module.get("root") or "")
        if not module_root.startswith(WOOBE_CORE_MODULES_ROOT):
            continue

        constraints = policy.get("constraints") or {}
        if constraints.get("forbid_cross_module_imports") is not True:
            relaxed.append(str(module.get("name") or policy_file.stem))

    assert not relaxed, (
        "woobe-core modules are service boundaries and cannot import another "
        f"module; cross-module imports were relaxed for: {', '.join(relaxed)}"
    )
