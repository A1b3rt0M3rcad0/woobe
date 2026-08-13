from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANONICAL_TEST_COMMAND = (
    "docker compose -f compose.test.yaml up --build --exit-code-from tests tests"
)


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
    assert (ROOT / "compose.test.yaml").is_file()
    assert (ROOT / "deploy/dev/compose.yml").is_file()

    for path in (
        "compose.yml",
        "docker-compose.yml",
        "docker-compose.community.yml",
        "docker-compose.prod.yml",
        "docker-compose.override.yml",
        "docker-compose.rabbitmq-observer.yml",
        "docker/rabbitmq",
        "deploy/test",
    ):
        assert not (ROOT / path).exists(), path


def test_test_topology_is_standalone_and_shell_independent() -> None:
    compose = (ROOT / "compose.test.yaml").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
    testing_docs = (ROOT / "docs/testing/COMPOSE_TESTS.md").read_text(encoding="utf-8")

    assert "name: woobe-test" in compose
    assert "backend-tests:" in compose
    assert "frontend-tests:" in compose
    assert "browser-mocked:" in compose
    assert "browser-e2e:" in compose
    assert "tests:" in compose
    assert "host.docker.internal" not in compose
    assert "deploy/test" not in compose
    assert "target: test" not in compose
    assert "ruff check src tests migrations" not in compose
    assert "npm run test:run" not in compose
    assert not (ROOT / "scripts/test.sh").exists()

    assert CANONICAL_TEST_COMMAND in workflow
    assert CANONICAL_TEST_COMMAND in testing_docs
    assert "docker compose -f compose.test.yaml run --rm tests" not in workflow
    assert "backend-pyright.log" in testing_docs
    assert "non-blocking repository baseline" in testing_docs
    assert "scripts/test.sh" not in workflow


def test_test_images_are_explicit_and_separate_from_product_dockerfiles() -> None:
    dockerfiles = {
        "backend": ROOT / "docker/tests/Dockerfile.backend",
        "frontend": ROOT / "docker/tests/Dockerfile.frontend",
        "browser-mocked": ROOT / "docker/tests/Dockerfile.browser-mocked",
        "browser-e2e": ROOT / "docker/tests/Dockerfile.browser-e2e",
        "fake-llm": ROOT / "docker/tests/Dockerfile.fake-llm",
    }
    for path in dockerfiles.values():
        assert path.is_file(), path

    compose = (ROOT / "compose.test.yaml").read_text(encoding="utf-8")
    for name in dockerfiles:
        assert f"Dockerfile.{name}" in compose

    backend_test = dockerfiles["backend"].read_text(encoding="utf-8")
    assert "pyright_status=0" in backend_test
    assert "backend-pyright.log" in backend_test
    assert 'if [ \"$pyright_status\" -eq 1 ]' in backend_test

    backend_product = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    frontend_product = (ROOT / "web/Dockerfile").read_text(encoding="utf-8")
    assert " AS test" not in backend_product
    assert " AS test" not in frontend_product
    assert not (ROOT / "e2e/Dockerfile").exists()


def test_browser_e2e_contract_is_present() -> None:
    assert (ROOT / "e2e/package.json").is_file()
    assert (ROOT / "e2e/fullstack.config.ts").is_file()
    assert (ROOT / "e2e/fullstack/community-bootstrap.spec.ts").is_file()


def test_runtime_documentation_uses_durable_product_paths() -> None:
    for path in (
        "docs/runtime/CHAT_SURFACE.md",
        "docs/runtime/MCP_TOOLS.md",
        "docs/runtime/STREAMING.md",
        "docs/testing/COMPOSE_TESTS.md",
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
