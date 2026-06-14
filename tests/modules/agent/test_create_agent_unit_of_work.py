"""Tests for spec 074 — create agent unit of work."""
import inspect

import pytest

from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.config.interface.unit_of_work import UnitOfWork


class TestAgentUnitOfWorkContract:
    """Verify AgentUnitOfWork implements the expected contract."""

    def test_inherits_from_unit_of_work(self):
        assert issubclass(AgentUnitOfWork, UnitOfWork)

    def test_init_accepts_session_factory(self):
        sig = inspect.signature(AgentUnitOfWork.__init__)
        params = list(sig.parameters.keys())
        assert "session_factory" in params

    def test_has_commit(self):
        assert hasattr(AgentUnitOfWork, "commit")
        assert inspect.iscoroutinefunction(AgentUnitOfWork.commit)

    def test_has_rollback(self):
        assert hasattr(AgentUnitOfWork, "rollback")
        assert inspect.iscoroutinefunction(AgentUnitOfWork.rollback)

    def test_has_aenter(self):
        assert hasattr(AgentUnitOfWork, "__aenter__")
        assert inspect.iscoroutinefunction(AgentUnitOfWork.__aenter__)

    def test_has_aexit(self):
        assert hasattr(AgentUnitOfWork, "__aexit__")
        assert inspect.iscoroutinefunction(AgentUnitOfWork.__aexit__)


class TestAgentUnitOfWorkRepositories:
    """Verify all required repositories are exposed."""

    REQUIRED_REPOS = [
        "agents",
        "provider_credentials",
        "sessions",
        "messages",
        "ask_jobs",
        "document_collections",
        "documents",
        "document_chunks",
        "knowledge_versions",
        "outbox",
        "inbox",
    ]

    def test_all_required_repos_exist_as_properties(self):
        for repo_name in self.REQUIRED_REPOS:
            assert hasattr(AgentUnitOfWork, repo_name), f"Missing repo: {repo_name}"
            prop = getattr(AgentUnitOfWork, repo_name)
            assert isinstance(prop, property), f"{repo_name} should be a property"

    def test_session_property_exists(self):
        assert hasattr(AgentUnitOfWork, "session")
        prop = getattr(AgentUnitOfWork, "session")
        assert isinstance(prop, property)


class TestAgentUnitOfWorkForbiddenRepos:
    """Verify no cross-module repositories are exposed."""

    FORBIDDEN_REPOS = [
        "metering",
        "observability",
        "billing",
        "identity",
        "tools",
        "core",
    ]

    def test_no_forbidden_repos(self):
        members = dir(AgentUnitOfWork)
        for forbidden in self.FORBIDDEN_REPOS:
            assert forbidden not in members, (
                f"AgentUnitOfWork must not expose '{forbidden}' repository"
            )

    def test_no_cross_module_imports_in_unit_of_work(self):
        source = inspect.getsource(AgentUnitOfWork)
        forbidden_patterns = [
            "modules.metering",
            "modules.observability",
            "modules.billing",
            "modules.identity",
            "modules.tools",
            "modules.core",
        ]
        for pattern in forbidden_patterns:
            assert pattern not in source, (
                f"AgentUnitOfWork must not import from '{pattern}'"
            )


class TestAgentUnitOfWorkIdempotency:
    """Verify outbox is accessible for idempotent event writing."""

    def test_outbox_repo_has_add(self):
        from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxRepository
        assert hasattr(SQLAlchemyAgentOutboxRepository, "add")

    def test_outbox_model_has_unique_idempotency_key(self):
        from sqlalchemy import UniqueConstraint as UC
        from modules.agent.infra.database.models import AgentOutboxEventModel
        table = AgentOutboxEventModel.__table__
        uq = [
            c for c in table.constraints
            if isinstance(c, UC) and "idempotency_key" in {col.name for col in c.columns}
        ]
        assert len(uq) == 1


class TestAgentUnitOfWorkConcurrency:
    """Verify outbox/inbox claim operations are available via UoW."""

    def test_outbox_repo_has_claim_batch(self):
        from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxRepository
        assert hasattr(SQLAlchemyAgentOutboxRepository, "claim_batch")
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "skip_locked" in source

    def test_inbox_repo_has_claim_batch(self):
        from modules.agent.infra.database.repositories import SQLAlchemyAgentInboxRepository
        assert hasattr(SQLAlchemyAgentInboxRepository, "claim_batch")
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "skip_locked" in source


class TestAgentUnitOfWorkSessionLifecycle:
    """Verify session is not started until __aenter__."""

    def test_session_raises_before_enter(self):
        from unittest.mock import MagicMock
        factory = MagicMock()
        uow = AgentUnitOfWork(factory)
        with pytest.raises(RuntimeError, match="session not started"):
            _ = uow.session
