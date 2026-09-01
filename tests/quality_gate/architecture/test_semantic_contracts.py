from pathlib import Path

from quality_gate.architecture.checker import ArchitectureChecker
from quality_gate.architecture.policy import load_policy


PROJECT_ROOT = Path(__file__).resolve().parents[3]
POLICY_SOURCE = (
    PROJECT_ROOT
    / "tooling/quality-gate/src/quality_gate/architecture/policies/agent.toml"
)
CORE_SOURCE = Path("packages/woobe-core/src")


def _setup(tmp_path: Path) -> tuple[ArchitectureChecker, object, Path]:
    source_root = tmp_path / CORE_SOURCE
    module = source_root / "modules/agent"
    for layer in (
        "domain",
        "application/interfaces",
        "application/use_cases",
        "infra/database",
        "presentation/controllers",
        "composition/composers",
    ):
        (module / layer).mkdir(parents=True, exist_ok=True)
    (source_root / "shared/contracts").mkdir(parents=True, exist_ok=True)
    (source_root / "shared/infra/repositories").mkdir(parents=True, exist_ok=True)
    (source_root / "shared/contracts/unit_of_work.py").write_text(
        "from abc import ABC\nclass UnitOfWork(ABC): pass\n", encoding="utf-8"
    )
    (source_root / "shared/infra/repositories/base_repository.py").write_text(
        "class BaseSQLAlchemyRepository: pass\n", encoding="utf-8"
    )
    (module / "domain/entities.py").write_text("VALUE = 1\n", encoding="utf-8")
    (module / "application/interfaces/repositories.py").write_text(
        "from abc import ABC\nclass AgentRepository(ABC): pass\n", encoding="utf-8"
    )
    (module / "application/use_cases/example.py").write_text(
        "class Example:\n    def __init__(self, repo: object): self.repo = repo\n", encoding="utf-8"
    )
    (module / "infra/database/unit_of_work.py").write_text(
        "class AgentUnitOfWork:\n    @property\n    def session(self): return None\n", encoding="utf-8"
    )
    (module / "infra/database/repositories.py").write_text(
        "class SQLAlchemyAgentRepository(AgentRepository): pass\n", encoding="utf-8"
    )
    (module / "presentation/routes.py").write_text("VALUE = 1\n", encoding="utf-8")
    (module / "presentation/controllers/example.py").write_text("VALUE = 1\n", encoding="utf-8")
    (module / "composition/composers/example.py").write_text(
        "def example_composer(database) -> TransactionalHandler:\n"
        "    uow = AgentUnitOfWork(database)\n"
        "    repo = SQLAlchemyAgentRepository(uow)\n"
        "    return TransactionalHandler(uow, handler)\n",
        encoding="utf-8",
    )
    policy_path = tmp_path / "agent.toml"
    policy_path.write_text(POLICY_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    return ArchitectureChecker(tmp_path), load_policy(policy_path, project_root=tmp_path), module


def test_strict_composer_rejects_framework_signature_control_flow_nested_defs_and_uow_locator(tmp_path: Path) -> None:
    checker, policy, module = _setup(tmp_path)
    (module / "composition/composers/example.py").write_text(
        "def example_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:\n"
        "    uow = AgentUnitOfWork(session_factory)\n"
        "    repo = uow.agents\n"
        "    if repo:\n"
        "        pass\n"
        "    def helper():\n"
        "        return 1\n"
        "    return TransactionalHandler(uow, handler)\n",
        encoding="utf-8",
    )
    result = checker.check(policy)
    ids = {item.rule_id for item in result.violations}
    assert {"ARCH027", "ARCH028", "ARCH029", "ARCH051", "ARCH052"}.issubset(ids)


def test_uow_contract_must_be_framework_neutral_and_transaction_only(tmp_path: Path) -> None:
    checker, policy, module = _setup(tmp_path)
    source_root = tmp_path / CORE_SOURCE
    shared_contract = source_root / "shared/contracts/unit_of_work.py"
    shared_contract.write_text("from sqlalchemy.ext.asyncio import AsyncSession\n", encoding="utf-8")
    (source_root / "shared/infra/config/interface").mkdir(parents=True)
    (source_root / "shared/infra/config/interface/unit_of_work.py").write_text("VALUE=1\n", encoding="utf-8")
    (module / "infra/database/unit_of_work.py").write_text(
        "from modules.agent.infra.database.repositories import SQLAlchemyAgentRepository\n"
        "class AgentUnitOfWork:\n"
        "    @property\n"
        "    def session(self): return None\n"
        "    @property\n"
        "    def agents(self): return SQLAlchemyAgentRepository(self)\n",
        encoding="utf-8",
    )
    result = checker.check(policy)
    ids = {item.rule_id for item in result.violations}
    assert {"ARCH032", "ARCH033", "ARCH034"}.issubset(ids)


def test_repository_contract_rejects_framework_port_missing_port_base_direct_session_and_commit(tmp_path: Path) -> None:
    checker, policy, module = _setup(tmp_path)
    (module / "application/interfaces/repositories.py").write_text(
        "from sqlalchemy.ext.asyncio import AsyncSession\nclass AgentRepository: pass\n",
        encoding="utf-8",
    )
    (module / "infra/database/repositories.py").write_text(
        "class SQLAlchemyOrphanRepository(BaseSQLAlchemyRepository):\n"
        "    def __init__(self, session: AsyncSession): pass\n"
        "    async def save(self):\n"
        "        await self.session.commit()\n",
        encoding="utf-8",
    )
    result = checker.check(policy)
    ids = {item.rule_id for item in result.violations}
    assert {"ARCH035", "ARCH037", "ARCH038", "ARCH039"}.issubset(ids)


def test_application_dependency_requires_explicit_port_type(tmp_path: Path) -> None:
    checker, policy, module = _setup(tmp_path)
    (module / "application/use_cases/example.py").write_text(
        "class Example:\n    def __init__(self, provider_model_repo=None): self.repo = provider_model_repo\n",
        encoding="utf-8",
    )
    result = checker.check(policy)
    assert any(item.rule_id == "ARCH040" for item in result.violations)


def test_presentation_cannot_import_composition(tmp_path: Path) -> None:
    checker, policy, module = _setup(tmp_path)
    (module / "presentation/routes.py").write_text(
        "from modules.agent.composition.composers.example import example_composer\n",
        encoding="utf-8",
    )
    result = checker.check(policy)
    assert any(item.rule_id == "ARCH006" for item in result.violations)
