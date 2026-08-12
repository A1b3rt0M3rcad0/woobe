from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_internal_workspace_artifacts_are_not_part_of_public_head() -> None:
    for path in (
        ".opencode",
        "opencode.json",
        "specs",
        "docs/mvp",
        "docs/modal-format.md",
        "docs/mcp-tools-mvp.md",
        "scripts/rename_metadata.py",
    ):
        assert not (ROOT / path).exists(), path


def test_public_deployment_surface_has_one_default_contract() -> None:
    assert (ROOT / "compose.yaml").is_file()
    assert (ROOT / "deploy/dev/compose.yml").is_file()
    assert (ROOT / "deploy/test/compose.yml").is_file()
    assert (ROOT / "deploy/test/test.env").is_file()

    for path in (
        "compose.yml",
        "docker-compose.yml",
        "docker-compose.community.yml",
        "docker-compose.prod.yml",
        "docker-compose.override.yml",
        "docker-compose.rabbitmq-observer.yml",
        "docker/rabbitmq",
    ):
        assert not (ROOT / path).exists(), path


def test_test_topology_is_a_validation_contract_not_a_distribution() -> None:
    assert (ROOT / "scripts/test.sh").is_file()
    assert (ROOT / "e2e/package.json").is_file()
    assert (ROOT / "e2e/Dockerfile").is_file()
    assert (ROOT / "e2e/fullstack.config.ts").is_file()
    assert (ROOT / "e2e/fullstack/community-bootstrap.spec.ts").is_file()


def test_runtime_documentation_uses_durable_product_paths() -> None:
    for path in (
        "docs/runtime/CHAT_SURFACE.md",
        "docs/runtime/MCP_TOOLS.md",
        "docs/runtime/STREAMING.md",
    ):
        assert (ROOT / path).is_file(), path


def test_manual_workflow_surface_is_consolidated() -> None:
    workflow_dir = ROOT / ".github/workflows"
    actual = {path.name for path in workflow_dir.glob("*.yml")}
    assert actual == {
        "acceptance.yml",
        "containers.yml",
        "release.yml",
        "security.yml",
        "tests.yml",
    }


def test_browser_e2e_namespace_is_not_duplicated_under_python_tests() -> None:
    assert not (ROOT / "tests/e2e").exists()
    assert (ROOT / "e2e/tests").is_dir()


def test_pull_request_template_is_canonical() -> None:
    assert (ROOT / ".github/PULL_REQUEST_TEMPLATE.md").is_file()
    assert not (ROOT / ".github/pull_request_template.md").exists()
