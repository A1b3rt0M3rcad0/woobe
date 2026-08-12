from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_internal_workspace_artifacts_are_not_part_of_public_head() -> None:
    for path in (
        ".opencode",
        "specs",
        "docs/mvp",
        "docs/modal-format.md",
        "docs/mcp-tools-mvp.md",
    ):
        assert not (ROOT / path).exists(), path


def test_public_deployment_surface_has_one_default_contract() -> None:
    assert (ROOT / "compose.yml").is_file()
    assert (ROOT / "deploy/dev/compose.yml").is_file()

    for path in (
        "docker-compose.yml",
        "docker-compose.community.yml",
        "docker-compose.prod.yml",
        "docker-compose.override.yml",
        "docker-compose.rabbitmq-observer.yml",
        "docker/rabbitmq",
    ):
        assert not (ROOT / path).exists(), path


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
