from pathlib import Path
import tomllib

from quality_gate.architecture.policy import load_policies


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODULES_ROOT = PROJECT_ROOT / "packages/woobe-core/src/modules"
POLICY_DIR = (
    PROJECT_ROOT
    / "tooling/quality-gate/src/quality_gate/architecture/policies"
)
RESPONSIBILITY_DIR = (
    PROJECT_ROOT
    / "tooling/quality-gate/src/quality_gate/architecture/responsibilities"
)


def _bounded_contexts() -> set[str]:
    return {
        path.name
        for path in MODULES_ROOT.iterdir()
        if path.is_dir() and not path.name.startswith("_")
    }


def test_every_core_bounded_context_has_an_architecture_policy() -> None:
    modules = _bounded_contexts()
    policies = load_policies(POLICY_DIR, project_root=PROJECT_ROOT)
    governed = {policy.name for policy in policies}
    assert governed == modules, (
        "architecture policy coverage mismatch; "
        f"missing={sorted(modules - governed)}, "
        f"unknown={sorted(governed - modules)}"
    )


def test_every_core_bounded_context_has_a_responsibility_contract() -> None:
    modules = _bounded_contexts()
    governed = {path.stem for path in RESPONSIBILITY_DIR.glob("*.toml")}
    assert governed == modules, (
        "responsibility contract coverage mismatch; "
        f"missing={sorted(modules - governed)}, "
        f"unknown={sorted(governed - modules)}"
    )


def test_policy_identity_matches_module_path_and_package() -> None:
    for policy in load_policies(POLICY_DIR, project_root=PROJECT_ROOT):
        expected_root = MODULES_ROOT / policy.name
        assert policy.root == expected_root
        assert policy.package == f"modules.{policy.name}"


def test_transaction_contracts_cover_every_database_backed_module() -> None:
    expected = _bounded_contexts()
    governed: set[str] = set()
    contract_dir = POLICY_DIR / "contracts"
    for path in contract_dir.glob("*_transaction_ownership.toml"):
        with path.open("rb") as stream:
            raw = tomllib.load(stream)["transaction_ownership"]
        governed.add(
            str(
                raw.get("module")
                or path.stem.removesuffix("_transaction_ownership")
            )
        )
    assert governed == expected, (
        "transaction ownership coverage mismatch; "
        f"missing={sorted(expected - governed)}, "
        f"unknown={sorted(governed - expected)}"
    )
