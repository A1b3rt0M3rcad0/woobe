from datetime import datetime, timezone
from uuid import UUID
from unittest.mock import AsyncMock

import pytest

from modules.identity.application.use_cases import (
    CreateUserUseCase,
    ListWorkspacesUseCase,
    GetWorkspaceUseCase,
    GetUserUseCase,
    GetCurrentUserUseCase,
)
from modules.identity.application.dtos import (
    CreateUserInput,
    ListWorkspacesInput,
    GetWorkspaceInput,
    GetUserInput,
    GetCurrentUserInput,
)
from modules.identity.domain.entities import User, Workspace
from modules.identity.domain.enums import UserStatus, WorkspaceStatus


class TestCreateUserUseCase:
    @pytest.mark.anyio
    async def test_create_user_success(self):
        user_repo = AsyncMock()
        user_repo.get_by_email.return_value = None
        user_repo.save.return_value = User(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            email="test@example.com",
            status=UserStatus.active,
            created_at=datetime.now(timezone.utc),
        )

        outbox = AsyncMock()
        use_case = CreateUserUseCase(user_repo, outbox)
        result = await use_case.execute(CreateUserInput(
            email="test@example.com",
            password="secret123",
        ))

        assert result.id == UUID("00000000-0000-0000-0000-000000000001")
        assert result.email == "test@example.com"
        assert result.status == UserStatus.active
        user_repo.get_by_email.assert_called_once_with("test@example.com")
        outbox.write.assert_called_once()


class TestListWorkspacesUseCase:
    @pytest.mark.anyio
    async def test_list_workspaces(self):
        workspace_repo = AsyncMock()
        workspace_repo.list_all.return_value = [
            Workspace(id=UUID("00000000-0000-0000-0000-000000000001"), name="Workspace A"),
            Workspace(id=UUID("00000000-0000-0000-0000-000000000002"), name="Workspace B"),
        ]

        use_case = ListWorkspacesUseCase(workspace_repo)
        result = await use_case.execute(ListWorkspacesInput())

        assert len(result) == 2
        assert result[0].name == "Workspace A"


class TestGetWorkspaceUseCase:
    @pytest.mark.anyio
    async def test_get_workspace_found(self):
        workspace_repo = AsyncMock()
        workspace_repo.get_by_id.return_value = Workspace(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            name="Test Workspace",
            status=WorkspaceStatus.active,
        )

        use_case = GetWorkspaceUseCase(workspace_repo)
        result = await use_case.execute(GetWorkspaceInput(
            workspace_id=UUID("00000000-0000-0000-0000-000000000001"),
        ))

        assert result is not None
        assert result.name == "Test Workspace"
        assert result.status == WorkspaceStatus.active


class TestGetUserUseCase:
    @pytest.mark.anyio
    async def test_get_user_found(self):
        user_repo = AsyncMock()
        user_repo.get_by_id.return_value = User(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            email="user@example.com",
            status=UserStatus.active,
        )

        use_case = GetUserUseCase(user_repo)
        result = await use_case.execute(GetUserInput(
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
        ))

        assert result is not None
        assert result.email == "user@example.com"


class TestGetCurrentUserUseCase:
    @pytest.mark.anyio
    async def test_get_current_user(self):
        use_case = GetCurrentUserUseCase()
        result = await use_case.execute(GetCurrentUserInput())

        assert result.email == "customer@gmail.com"
