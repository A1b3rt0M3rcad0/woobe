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

    for path in (
        "compose.yml",
        "docker-compose.yml",
        "docker-compose.yaml",
        "docker-compose.community.yml",
        "docker-compose.prod.yml",
        "docker-compose.override.yml",
        "docker-compose.rabbitmq-observer.yml",
        "docker/rabbitmq",
    ):
        assert not (ROOT / path).exists(), path


def test_repository_has_one_pull_request_template() -> None:
    assert (ROOT / ".github/PULL_REQUEST_TEMPLATE.md").is_file()
    assert not (ROOT / ".github/pull_request_template.md").exists()


def test_browser_e2e_has_a_single_public_namespace() -> None:
    assert (ROOT / "e2e").is_dir()
    assert not (ROOT / "tests/e2e").exists()


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
        "backend.yml",
        "containers.yml",
        "frontend.yml",
        "release.yml",
        "security.yml",
    }
