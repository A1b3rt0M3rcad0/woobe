import pytest

from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


class TestAgentUnitOfWork:
    async def test_uow_exposes_session_only_inside_transaction(self):
        from unittest.mock import AsyncMock, MagicMock

        mock_session = AsyncMock()
        session_factory = MagicMock(return_value=mock_session)
        uow = AgentUnitOfWork(session_factory)

        with pytest.raises(RuntimeError, match="session not started"):
            _ = uow.session

        async with uow:
            assert uow.session is mock_session

        with pytest.raises(RuntimeError, match="session not started"):
            _ = uow.session

    async def test_uow_has_no_repository_service_locator(self):
        from unittest.mock import MagicMock

        uow = AgentUnitOfWork(MagicMock())

        assert not hasattr(uow, "tools")
        assert not hasattr(uow, "tool_secrets")
        assert not hasattr(uow, "agents")

    async def test_repositories_are_composed_explicitly_from_same_uow(self):
        from unittest.mock import AsyncMock, MagicMock

        from modules.agent.infra.database.repositories import (
            SQLAlchemyAgentToolRepository,
            SQLAlchemyAgentToolSecretRepository,
        )

        mock_session = AsyncMock()
        session_factory = MagicMock(return_value=mock_session)
        uow = AgentUnitOfWork(session_factory)

        async with uow:
            tools = SQLAlchemyAgentToolRepository(uow)
            secrets = SQLAlchemyAgentToolSecretRepository(uow)

            assert tools._session is mock_session
            assert secrets._session is mock_session
            assert tools is not secrets


class TestUnitOfWorkCommitRollback:
    async def test_commit_called_on_success(self):
        from unittest.mock import AsyncMock, MagicMock

        mock_session = AsyncMock()
        session_factory = MagicMock(return_value=mock_session)
        uow = AgentUnitOfWork(session_factory)

        async with uow:
            pass

        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_called()
        mock_session.close.assert_awaited_once()

    async def test_rollback_called_on_error(self):
        from unittest.mock import AsyncMock, MagicMock

        mock_session = AsyncMock()
        session_factory = MagicMock(return_value=mock_session)
        uow = AgentUnitOfWork(session_factory)

        class TestError(Exception):
            pass

        with pytest.raises(TestError):
            async with uow:
                raise TestError()

        mock_session.rollback.assert_awaited_once()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_awaited_once()


class TestAgentRepositoryComposition:
    async def test_tool_repository_uses_agent_uow_session(self):
        from unittest.mock import AsyncMock, MagicMock

        from modules.agent.infra.database.repositories import SQLAlchemyAgentToolRepository

        mock_session = AsyncMock()
        uow = AgentUnitOfWork(MagicMock(return_value=mock_session))

        async with uow:
            repository = SQLAlchemyAgentToolRepository(uow)
            assert repository._session is uow.session

    async def test_tool_secret_repository_uses_agent_uow_session(self):
        from unittest.mock import AsyncMock, MagicMock

        from modules.agent.infra.database.repositories import (
            SQLAlchemyAgentToolSecretRepository,
        )

        mock_session = AsyncMock()
        uow = AgentUnitOfWork(MagicMock(return_value=mock_session))

        async with uow:
            repository = SQLAlchemyAgentToolSecretRepository(uow)
            assert repository._session is uow.session
