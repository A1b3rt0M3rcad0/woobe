from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from modules.agent.infra.database import unit_of_work as unit_of_work_module
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def _build_mocked_uow(monkeypatch):
    engine = MagicMock(spec=AsyncEngine)
    session = AsyncMock(spec=AsyncSession)
    session_factory = MagicMock(return_value=session)
    async_sessionmaker = MagicMock(return_value=session_factory)
    monkeypatch.setattr(
        unit_of_work_module,
        "async_sessionmaker",
        async_sessionmaker,
    )
    return AgentUnitOfWork(engine), engine, session, async_sessionmaker, session_factory


class TestAgentUnitOfWork:
    async def test_uow_exposes_session_only_inside_transaction(self, monkeypatch):
        uow, engine, session, async_sessionmaker, session_factory = _build_mocked_uow(
            monkeypatch
        )

        with pytest.raises(RuntimeError, match="session not started"):
            _ = uow.session

        async with uow:
            assert uow.session is session

        async_sessionmaker.assert_called_once_with(
            bind=engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        session_factory.assert_called_once_with()

        with pytest.raises(RuntimeError, match="session not started"):
            _ = uow.session

    async def test_uow_has_no_repository_service_locator(self):
        uow = AgentUnitOfWork(MagicMock(spec=AsyncEngine))

        assert not hasattr(uow, "tools")
        assert not hasattr(uow, "tool_secrets")
        assert not hasattr(uow, "agents")

    async def test_repositories_are_composed_explicitly_from_same_uow(
        self,
        monkeypatch,
    ):
        from modules.agent.infra.database.repositories import (
            SQLAlchemyAgentToolRepository,
            SQLAlchemyAgentToolSecretRepository,
        )

        uow, _, session, _, _ = _build_mocked_uow(monkeypatch)

        async with uow:
            tools = SQLAlchemyAgentToolRepository(uow)
            secrets = SQLAlchemyAgentToolSecretRepository(uow)

            assert tools._session is session
            assert secrets._session is session
            assert tools is not secrets


class TestUnitOfWorkCommitRollback:
    async def test_commit_called_on_success(self, monkeypatch):
        uow, _, session, _, _ = _build_mocked_uow(monkeypatch)

        async with uow:
            pass

        session.commit.assert_awaited_once()
        session.rollback.assert_not_called()
        session.close.assert_awaited_once()

    async def test_rollback_called_on_error(self, monkeypatch):
        uow, _, session, _, _ = _build_mocked_uow(monkeypatch)

        class TestError(Exception):
            pass

        with pytest.raises(TestError):
            async with uow:
                raise TestError()

        session.rollback.assert_awaited_once()
        session.commit.assert_not_called()
        session.close.assert_awaited_once()


class TestAgentRepositoryComposition:
    async def test_tool_repository_uses_agent_uow_session(self, monkeypatch):
        from modules.agent.infra.database.repositories import SQLAlchemyAgentToolRepository

        uow, _, session, _, _ = _build_mocked_uow(monkeypatch)

        async with uow:
            repository = SQLAlchemyAgentToolRepository(uow)
            assert repository._session is session
            assert repository._session is uow.session

    async def test_tool_secret_repository_uses_agent_uow_session(self, monkeypatch):
        from modules.agent.infra.database.repositories import (
            SQLAlchemyAgentToolSecretRepository,
        )

        uow, _, session, _, _ = _build_mocked_uow(monkeypatch)

        async with uow:
            repository = SQLAlchemyAgentToolSecretRepository(uow)
            assert repository._session is session
            assert repository._session is uow.session
