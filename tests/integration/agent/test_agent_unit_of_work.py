
import pytest

from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


class TestAgentUnitOfWork:

    async def test_uow_provides_tool_repo(self):
        from unittest.mock import AsyncMock, MagicMock

        session_factory = MagicMock()
        session_factory.return_value = AsyncMock()
        uow = AgentUnitOfWork(session_factory)

        async with uow:
            repo = uow.tools
            assert repo is not None

    async def test_uow_provides_tool_secret_repo(self):
        from unittest.mock import AsyncMock, MagicMock

        session_factory = MagicMock()
        session_factory.return_value = AsyncMock()
        uow = AgentUnitOfWork(session_factory)

        async with uow:
            repo = uow.tool_secrets
            assert repo is not None

    async def test_uow_tools_and_secrets_are_distinct(self):
        from unittest.mock import AsyncMock, MagicMock

        session_factory = MagicMock()
        session_factory.return_value = AsyncMock()
        uow = AgentUnitOfWork(session_factory)

        async with uow:
            tools = uow.tools
            secrets = uow.tool_secrets
            assert tools is not None
            assert secrets is not None
            assert tools is not secrets

    async def test_uow_resets_repos_after_exit(self):
        from unittest.mock import AsyncMock, MagicMock

        session_factory = MagicMock()
        session_factory.return_value = AsyncMock()
        uow = AgentUnitOfWork(session_factory)

        async with uow:
            _ = uow.tools
            assert uow._tools is not None

        assert uow._tools is None
        assert uow._tool_secrets is None


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


class TestAgentUnitOfWorkIntegration:
    """Integration-level tests for AgentUnitOfWork with tool/secrets.

    These tests validate the behavior at the composite level:
    UoW → repositories → models.
    """

    async def test_tool_repo_is_sqlalchemy_agent_tool_repo(self):
        from unittest.mock import AsyncMock, MagicMock
        from modules.agent.infra.database.repositories import SQLAlchemyAgentToolRepository

        session_factory = MagicMock()
        session_factory.return_value = AsyncMock()
        uow = AgentUnitOfWork(session_factory)

        async with uow:
            assert isinstance(uow.tools, SQLAlchemyAgentToolRepository)

    async def test_tool_secret_repo_is_sqlalchemy_agent_secret_repo(self):
        from unittest.mock import AsyncMock, MagicMock
        from modules.agent.infra.database.repositories import SQLAlchemyAgentToolSecretRepository

        session_factory = MagicMock()
        session_factory.return_value = AsyncMock()
        uow = AgentUnitOfWork(session_factory)

        async with uow:
            assert isinstance(uow.tool_secrets, SQLAlchemyAgentToolSecretRepository)
