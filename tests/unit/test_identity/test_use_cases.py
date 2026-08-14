import uuid6
from datetime import UTC, datetime

import pytest

from modules.identity.domain.entities import WorkspaceInvite
from modules.identity.domain.enums import InviteStatus, MemberRole
from modules.identity.domain.errors import (
    EmailAlreadyExistsError,
    WorkspaceNotFoundError,
    UserNotFoundError,
)
from modules.identity.application.dtos import (
    AddMemberInput,
    CreateWorkspaceInput,
    CreateUserInput,
    InviteUserInput,
)
from modules.identity.application.use_cases import (
    AddMemberToWorkspaceUseCase,
    CreateWorkspaceUseCase,
    CreateUserUseCase,
    InviteUserUseCase,
)
from shared.infra.errors import ConflictError
from tests.helpers import make_workspace, make_workspace_member, make_user


class TestCreateUserUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        mock_repo = mocker.AsyncMock()
        mock_repo.get_by_email.return_value = None
        mock_repo.save.return_value = make_user(email="new@test.com")

        mock_outbox = mocker.AsyncMock()

        uc = CreateUserUseCase(user_repo=mock_repo, outbox=mock_outbox)
        result = await uc.execute(CreateUserInput(email="new@test.com", password="secret123"))

        assert result.email == "new@test.com"
        mock_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_duplicate_email(self, mocker):
        mock_repo = mocker.AsyncMock()
        mock_repo.get_by_email.return_value = make_user(email="dup@test.com")

        uc = CreateUserUseCase(user_repo=mock_repo, outbox=mocker.AsyncMock())
        with pytest.raises(EmailAlreadyExistsError):
            await uc.execute(CreateUserInput(email="dup@test.com", password="secret123"))
        mock_repo.save.assert_not_called()


class TestCreateWorkspaceUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        mock_repo = mocker.AsyncMock()
        mock_repo.get_by_slug.return_value = None
        mock_repo.save.return_value = make_workspace(name="TestWorkspace", slug="test-workspace")

        mock_outbox = mocker.AsyncMock()

        uc = CreateWorkspaceUseCase(workspace_repo=mock_repo, outbox=mock_outbox)
        result = await uc.execute(CreateWorkspaceInput(name="TestWorkspace", slug="test-workspace"))

        assert result.name == "TestWorkspace"
        assert result.slug == "test-workspace"
        mock_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_duplicate_slug(self, mocker):
        mock_repo = mocker.AsyncMock()
        mock_repo.get_by_slug.return_value = make_workspace(slug="dup-slug")

        uc = CreateWorkspaceUseCase(workspace_repo=mock_repo, outbox=mocker.AsyncMock())
        with pytest.raises(ConflictError):
            await uc.execute(CreateWorkspaceInput(name="TestWorkspace", slug="dup-slug"))
        mock_repo.save.assert_not_called()


class TestAddMemberToWorkspaceUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        workspace_id = uuid6.uuid7()
        user_id = uuid6.uuid7()

        mock_workspace_repo = mocker.AsyncMock()
        mock_workspace_repo.get_by_id.return_value = make_workspace()

        mock_user_repo = mocker.AsyncMock()
        mock_user_repo.get_by_id.return_value = make_user()

        mock_member_repo = mocker.AsyncMock()
        mock_member_repo.get_by_workspace_and_user.return_value = None
        mock_member_repo.save.return_value = make_workspace_member(
            user_id=user_id, workspace_id=workspace_id, role=MemberRole.member
        )

        mock_outbox = mocker.AsyncMock()

        uc = AddMemberToWorkspaceUseCase(
            workspace_repo=mock_workspace_repo,
            user_repo=mock_user_repo,
            member_repo=mock_member_repo,
            outbox=mock_outbox,
        )
        result = await uc.execute(
            AddMemberInput(user_id=user_id, workspace_id=workspace_id)
        )

        assert result.role == MemberRole.member
        mock_member_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_workspace_not_found(self, mocker):
        mock_workspace_repo = mocker.AsyncMock()
        mock_workspace_repo.get_by_id.return_value = None

        uc = AddMemberToWorkspaceUseCase(
            workspace_repo=mock_workspace_repo,
            user_repo=mocker.AsyncMock(),
            member_repo=mocker.AsyncMock(),
            outbox=mocker.AsyncMock(),
        )
        with pytest.raises(WorkspaceNotFoundError):
            await uc.execute(
                AddMemberInput(
                    user_id=uuid6.uuid7(),
                    workspace_id=uuid6.uuid7(),
                )
            )

    @pytest.mark.asyncio
    async def test_user_not_found(self, mocker):
        mock_workspace_repo = mocker.AsyncMock()
        mock_workspace_repo.get_by_id.return_value = make_workspace()

        mock_user_repo = mocker.AsyncMock()
        mock_user_repo.get_by_id.return_value = None

        uc = AddMemberToWorkspaceUseCase(
            workspace_repo=mock_workspace_repo,
            user_repo=mock_user_repo,
            member_repo=mocker.AsyncMock(),
            outbox=mocker.AsyncMock(),
        )
        with pytest.raises(UserNotFoundError):
            await uc.execute(
                AddMemberInput(
                    user_id=uuid6.uuid7(),
                    workspace_id=uuid6.uuid7(),
                )
            )

    @pytest.mark.asyncio
    async def test_already_member(self, mocker):
        workspace_id = uuid6.uuid7()
        user_id = uuid6.uuid7()

        mock_workspace_repo = mocker.AsyncMock()
        mock_workspace_repo.get_by_id.return_value = make_workspace()

        mock_user_repo = mocker.AsyncMock()
        mock_user_repo.get_by_id.return_value = make_user()

        mock_member_repo = mocker.AsyncMock()
        mock_member_repo.get_by_workspace_and_user.return_value = make_workspace_member()

        uc = AddMemberToWorkspaceUseCase(
            workspace_repo=mock_workspace_repo,
            user_repo=mock_user_repo,
            member_repo=mock_member_repo,
            outbox=mocker.AsyncMock(),
        )
        with pytest.raises(ConflictError):
            await uc.execute(
                AddMemberInput(user_id=user_id, workspace_id=workspace_id)
            )
        mock_member_repo.save.assert_not_called()


class TestInviteUserUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        workspace_id = uuid6.uuid7()

        mock_workspace_repo = mocker.AsyncMock()
        mock_workspace_repo.get_by_id.return_value = make_workspace()

        mock_invite_repo = mocker.AsyncMock()
        mock_invite_repo.get_by_workspace_and_email.return_value = None

        saved_invite = WorkspaceInvite(
            id=uuid6.uuid7(),
            workspace_id=workspace_id,
            email="invite@test.com",
            role=MemberRole.member,
            token_hash="tok",
            invited_by_user_id=uuid6.uuid7(),
            status=InviteStatus.pending,
            expires_at=datetime.now(UTC) + __import__("datetime").timedelta(days=7),
            created_at=datetime.now(UTC),
        )
        mock_invite_repo.save.return_value = saved_invite

        mock_outbox = mocker.AsyncMock()

        uc = InviteUserUseCase(
            workspace_repo=mock_workspace_repo,
            invite_repo=mock_invite_repo,
            outbox=mock_outbox,
        )
        result = await uc.execute(
            InviteUserInput(
                workspace_id=workspace_id,
                email="invite@test.com",
                invited_by_user_id=uuid6.uuid7(),
            )
        )

        assert result.email == "invite@test.com"
        assert result.status == InviteStatus.pending
        mock_invite_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_workspace_not_found(self, mocker):
        mock_workspace_repo = mocker.AsyncMock()
        mock_workspace_repo.get_by_id.return_value = None

        uc = InviteUserUseCase(
            workspace_repo=mock_workspace_repo,
            invite_repo=mocker.AsyncMock(),
            outbox=mocker.AsyncMock(),
        )
        with pytest.raises(WorkspaceNotFoundError):
            await uc.execute(
                InviteUserInput(
                    workspace_id=uuid6.uuid7(),
                    email="invite@test.com",
                    invited_by_user_id=uuid6.uuid7(),
                )
            )

    @pytest.mark.asyncio
    async def test_pending_invite_exists(self, mocker):
        workspace_id = uuid6.uuid7()

        mock_workspace_repo = mocker.AsyncMock()
        mock_workspace_repo.get_by_id.return_value = make_workspace()

        existing_invite = WorkspaceInvite(
            email="invite@test.com",
            workspace_id=workspace_id,
            status=InviteStatus.pending,
        )
        mock_invite_repo = mocker.AsyncMock()
        mock_invite_repo.get_by_workspace_and_email.return_value = existing_invite

        uc = InviteUserUseCase(
            workspace_repo=mock_workspace_repo,
            invite_repo=mock_invite_repo,
            outbox=mocker.AsyncMock(),
        )
        with pytest.raises(ConflictError):
            await uc.execute(
                InviteUserInput(
                    workspace_id=workspace_id,
                    email="invite@test.com",
                    invited_by_user_id=uuid6.uuid7(),
                )
            )
        mock_invite_repo.save.assert_not_called()
