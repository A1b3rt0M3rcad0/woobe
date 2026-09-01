from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANONICAL_TEST_COMMAND = (
    "docker compose -f compose.test.yaml up --build --exit-code-from tests tests"
)
PACKAGE_ROOTS = {
    "woobe-core",
    "woobe-api",
    "woobe-workers",
    "woobe-frontend",
    "woobe-db",
    "woobe-ee",
    "woobe-testkit",
    "woobe-mock",
    "woobe-e2e",
}
PYTHON_PACKAGE_ROOTS = {
    "woobe-core",
    "woobe-api",
    "woobe-workers",
    "woobe-testkit",
    "woobe-mock",
}


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


def test_package_workspace_is_the_public_source_surface() -> None:
    packages = ROOT / "packages"
    assert packages.is_dir()
    actual = {path.name for path in packages.iterdir() if path.is_dir()}
    assert PACKAGE_ROOTS.issubset(actual)

    for removed_root in ("src", "web", "embed", "migrations"):
        assert not (ROOT / removed_root).exists(), removed_root


def test_python_process_boundaries_have_install_metadata() -> None:
    for package in PYTHON_PACKAGE_ROOTS:
        pyproject = ROOT / "packages" / package / "pyproject.toml"
        assert pyproject.is_file(), f"{package} must define package installation metadata"
        content = pyproject.read_text(encoding="utf-8")
        assert "[build-system]" in content
        assert "[project]" in content


def test_enterprise_boundary_contains_no_proprietary_runtime_code() -> None:
    ee = ROOT / "packages/woobe-ee"
    assert (ee / "README.md").is_file()
    assert not (ee / "src").exists()
    for path in (
        "LICENSE-CLOUD.md",
        "LICENSE-ENTERPRISE.md",
    ):
        assert not (ROOT / path).exists(), path

    assert (ROOT / "LICENSE.md").is_file()
    assert (ROOT / "LICENSING.md").is_file()


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


def test_test_topology_is_backend_only_and_shell_independent() -> None:
    compose = (ROOT / "compose.test.yaml").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
    testing_docs = (ROOT / "docs/testing/COMPOSE_TESTS.md").read_text(encoding="utf-8")

    assert "name: woobe-test" in compose
    assert "backend-mocked:" in compose
    assert "backend-integration:" in compose
    assert "tests:" in compose
    assert "db:" in compose
    assert "rabbitmq:" in compose

    for forbidden in (
        "frontend-tests:",
        "browser-mocked:",
        "browser-e2e:",
        "web-mocked:",
        "chat-embed:",
        "playwright",
        "VITE_",
        "host.docker.internal",
        "deploy/test",
        "target: test",
    ):
        assert forbidden not in compose

    assert not (ROOT / "scripts/test.sh").exists()
    assert CANONICAL_TEST_COMMAND in workflow
    assert CANONICAL_TEST_COMMAND in testing_docs
    assert "frontend" not in workflow.lower()
    assert "playwright" not in workflow.lower()
    assert "scripts/test.sh" not in workflow


def test_runtime_python_packages_are_installed_without_pythonpath() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "PYTHONPATH=" not in dockerfile
    for package in ("woobe-core", "woobe-api", "woobe-workers"):
        assert f"--editable packages/{package}" in dockerfile


def test_backend_test_images_are_explicit_and_package_aware() -> None:
    mocked = ROOT / "docker/tests/Dockerfile.backend-mocked"
    integration = ROOT / "docker/tests/Dockerfile.backend-integration"
    assert mocked.is_file()
    assert integration.is_file()

    compose = (ROOT / "compose.test.yaml").read_text(encoding="utf-8")
    assert "Dockerfile.backend-mocked" in compose
    assert "Dockerfile.backend-integration" in compose

    mocked_text = mocked.read_text(encoding="utf-8")
    assert "python -m pytest -q tests/unit tests/fakes/test_openai_provider.py" in mocked_text
    assert "packages/woobe-core/src" in mocked_text
    assert "packages/woobe-api/src" in mocked_text
    assert "packages/woobe-workers/src" in mocked_text
    assert "PYTHONPATH=" not in mocked_text
    for package in ("woobe-core", "woobe-api", "woobe-workers", "woobe-testkit", "woobe-mock"):
        assert f"--editable packages/{package}" in mocked_text
    assert "test_billing" not in mocked_text
    for excluded in (
        "tests/modules",
        "tests/contract",
        "tests/messaging",
        "tests/editions",
        "tests/integration",
    ):
        assert excluded not in mocked_text

    integration_text = integration.read_text(encoding="utf-8")
    assert "alembic -c packages/woobe-db/alembic.ini upgrade head" in integration_text
    assert "python -m pytest -q tests/integration" in integration_text
    assert "PYTHONPATH=" not in integration_text
    for package in ("woobe-core", "woobe-api", "woobe-workers", "woobe-testkit", "woobe-mock"):
        assert f"--editable packages/{package}" in integration_text
    assert "tests/integration/billing" not in integration_text
    assert "tests/editions" not in integration_text
    assert "tests/migrations" not in integration_text

    for path in (
        "docker/tests/Dockerfile.backend",
        "docker/tests/Dockerfile.frontend",
        "docker/tests/Dockerfile.browser-mocked",
        "docker/tests/Dockerfile.browser-e2e",
        "docker/tests/Dockerfile.fake-llm",
    ):
        assert not (ROOT / path).exists(), path


def test_runtime_documentation_uses_durable_product_paths() -> None:
    for path in (
        "docs/runtime/CHAT_SURFACE.md",
        "docs/runtime/MCP_TOOLS.md",
        "docs/runtime/STREAMING.md",
        "docs/testing/COMPOSE_TESTS.md",
    ):
        assert (ROOT / path).is_file(), path


def test_workflow_surface_matches_repository_contracts() -> None:
    workflow_dir = ROOT / ".github/workflows"
    actual = {path.name for path in workflow_dir.glob("*.yml")}
    assert actual == {
        "acceptance.yml",
        "cla.yml",
        "containers.yml",
        "quality-gate.yml",
        "release.yml",
        "security.yml",
        "tests.yml",
    }


def test_pull_request_template_is_canonical() -> None:
    assert (ROOT / ".github/PULL_REQUEST_TEMPLATE.md").is_file()
    assert not (ROOT / ".github/pull_request_template.md").exists()
