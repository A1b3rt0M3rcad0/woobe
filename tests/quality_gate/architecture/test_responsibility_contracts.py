from pathlib import Path

from quality_gate.architecture.checker import ArchitectureChecker
from quality_gate.architecture.policy import load_policy


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESPONSIBILITY_SOURCE = (
    PROJECT_ROOT
    / "tooling"
    / "quality-gate"
    / "src"
    / "quality_gate"
    / "architecture"
    / "responsibilities"
    / "agent.toml"
)
CORE_SOURCE = Path("packages/woobe-core/src")
API_SOURCE = Path("packages/woobe-api/src")
WORKER_SOURCE = Path("packages/woobe-workers/src")

POLICY = """
[module]
name = "agent"
root = "packages/woobe-core/src/modules/agent"
package = "modules.agent"
required_layers = ["domain", "application", "infra", "presentation", "composition"]

[constraints]
forbid_cross_module_imports = false
forbid_dynamic_imports = false
forbid_wildcard_imports = false
forbid_cycles = false
forbidden_paths = []

[[rules]]
id = "ARCH900"
description = "responsibility contract fixture"
source = ["**"]
allow = []
deny = []
enforce_internal_allowlist = false
""".strip()


def _setup(tmp_path: Path) -> tuple[ArchitectureChecker, object, Path]:
    module = tmp_path / CORE_SOURCE / "modules/agent"
    for layer in ("domain", "application", "infra", "presentation", "composition"):
        (module / layer).mkdir(parents=True, exist_ok=True)
    (module / "domain/entities.py").write_text("VALUE = 1\n", encoding="utf-8")
    (module / "application/use_case.py").write_text("VALUE = 1\n", encoding="utf-8")
    (module / "infra/repository.py").write_text("VALUE = 1\n", encoding="utf-8")
    (module / "presentation/schema.py").write_text("VALUE = 1\n", encoding="utf-8")
    (module / "composition/__init__.py").write_text("", encoding="utf-8")
    (tmp_path / API_SOURCE).mkdir(parents=True, exist_ok=True)
    (tmp_path / WORKER_SOURCE / "woobe_workers/consumers/agent").mkdir(parents=True, exist_ok=True)

    policy_path = tmp_path / "agent-policy.toml"
    policy_path.write_text(POLICY, encoding="utf-8")

    responsibility_dir = tmp_path / "quality_gate/architecture/responsibilities"
    responsibility_dir.mkdir(parents=True, exist_ok=True)
    (responsibility_dir / "agent.toml").write_text(
        RESPONSIBILITY_SOURCE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return ArchitectureChecker(tmp_path), load_policy(policy_path, project_root=tmp_path), module


def _ids(checker: ArchitectureChecker, policy: object) -> set[str]:
    return {item.rule_id for item in checker.check(policy).violations}


def test_arch063_composition_surface_is_allowlisted(tmp_path: Path) -> None:
    checker, policy, module = _setup(tmp_path)
    path = module / "composition/runtime/service.py"
    path.parent.mkdir(parents=True)
    path.write_text("VALUE = 1\n", encoding="utf-8")
    assert "ARCH063" in _ids(checker, policy)


def test_arch064_http_transport_belongs_to_presentation_http(tmp_path: Path) -> None:
    checker, policy, module = _setup(tmp_path)
    path = module / "composition/http/routes.py"
    path.parent.mkdir(parents=True)
    path.write_text("from fastapi import APIRouter\n", encoding="utf-8")
    assert "ARCH064" in _ids(checker, policy)


def test_arch064_allows_fastapi_inside_presentation_http(tmp_path: Path) -> None:
    checker, policy, module = _setup(tmp_path)
    path = module / "presentation/http/routes.py"
    path.parent.mkdir(parents=True)
    path.write_text("from fastapi import APIRouter\n", encoding="utf-8")
    assert "ARCH064" not in _ids(checker, policy)


def test_arch065_presentation_cannot_use_app_state_as_service_locator(tmp_path: Path) -> None:
    checker, policy, module = _setup(tmp_path)
    path = module / "presentation/http/routes.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "def route(request):\n"
        "    return request.app.state.session_factory\n",
        encoding="utf-8",
    )
    assert "ARCH065" in _ids(checker, policy)


def test_arch066_application_runtime_is_framework_neutral(tmp_path: Path) -> None:
    checker, policy, module = _setup(tmp_path)
    path = module / "application/use_cases/runtime_service.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "from modules.agent.infra.database.unit_of_work import AgentUnitOfWork\n",
        encoding="utf-8",
    )
    assert "ARCH066" in _ids(checker, policy)


def test_arch067_concrete_runtime_gateway_belongs_to_infra(tmp_path: Path) -> None:
    checker, policy, module = _setup(tmp_path)
    path = module / "composition/factories/tool_runtime.py"
    path.parent.mkdir(parents=True)
    path.write_text("class AgentToolRuntimeGateway:\n    pass\n", encoding="utf-8")
    assert "ARCH067" in _ids(checker, policy)


def test_arch068_composition_cannot_execute_runtime_work(tmp_path: Path) -> None:
    checker, policy, module = _setup(tmp_path)
    path = module / "composition/factories/runtime.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "async def build_runtime(service):\n"
        "    return await service.execute()\n",
        encoding="utf-8",
    )
    assert "ARCH068" in _ids(checker, policy)


def test_arch069_use_cases_belong_to_application(tmp_path: Path) -> None:
    checker, policy, module = _setup(tmp_path)
    path = module / "composition/factories/use_case.py"
    path.parent.mkdir(parents=True)
    path.write_text("class RuntimeUseCase:\n    pass\n", encoding="utf-8")
    assert "ARCH069" in _ids(checker, policy)


def test_arch070_external_modules_cannot_import_agent_composition(tmp_path: Path) -> None:
    checker, policy, _ = _setup(tmp_path)
    path = tmp_path / CORE_SOURCE / "modules/network/bridge.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "from modules.agent.composition.runtime.gateway import Gateway\n",
        encoding="utf-8",
    )
    assert "ARCH070" in _ids(checker, policy)


def test_arch071_bootstrap_uses_agent_public_entrypoint(tmp_path: Path) -> None:
    checker, policy, _ = _setup(tmp_path)
    path = tmp_path / API_SOURCE / "main.py"
    path.write_text(
        "from modules.agent.infra.database.database import AgentDatabase\n",
        encoding="utf-8",
    )
    assert "ARCH071" in _ids(checker, policy)


def test_arch071_allows_agent_entrypoint(tmp_path: Path) -> None:
    checker, policy, _ = _setup(tmp_path)
    path = tmp_path / API_SOURCE / "main.py"
    path.write_text(
        "from modules.agent.entrypoint import build_internal_agent_runtime\n",
        encoding="utf-8",
    )
    assert "ARCH071" not in _ids(checker, policy)


def test_arch072_application_streaming_is_transport_neutral(tmp_path: Path) -> None:
    checker, policy, module = _setup(tmp_path)
    path = module / "application/use_cases/runtime_streaming.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "def serialize(value):\n"
        "    return f\"event: token\\ndata: {value}\\n\\n\"\n",
        encoding="utf-8",
    )
    assert "ARCH072" in _ids(checker, policy)


def test_arch071_worker_host_rejects_agent_internals(tmp_path: Path) -> None:
    checker, policy, _ = _setup(tmp_path)
    path = tmp_path / WORKER_SOURCE / "woobe_workers/consumers/agent/registry.py"
    path.write_text(
        "from modules.agent.infra.database.repositories import SQLAlchemyAgentRepository\n",
        encoding="utf-8",
    )
    assert "ARCH071" in _ids(checker, policy)


def test_arch071_worker_host_allows_agent_background_boundary(tmp_path: Path) -> None:
    checker, policy, _ = _setup(tmp_path)
    path = tmp_path / WORKER_SOURCE / "woobe_workers/consumers/agent/registry.py"
    path.write_text(
        "from modules.agent.background_boundary import SQLAlchemyAgentRepository\n",
        encoding="utf-8",
    )
    assert "ARCH071" not in _ids(checker, policy)
