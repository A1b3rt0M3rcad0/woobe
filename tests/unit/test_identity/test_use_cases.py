import uuid6
from datetime import UTC, datetime

import pytest

from modules.identity.domain.entities import Organization, OrganizationInvite, User
from modules.identity.domain.enums import InviteStatus, MemberRole
from modules.identity.domain.errors import (
    EmailAlreadyExistsError,
    OrganizationNotFoundError,
    UserNotFoundError,
)
from modules.identity.service.dtos import (
    AddMemberInput,
    CreateOrganizationInput,
    CreateUserInput,
    InviteUserInput,
)
from modules.identity.service.use_cases import (
    AddMemberToOrganizationUseCase,
    CreateOrganizationUseCase,
    CreateUserUseCase,
    InviteUserUseCase,
)
from shared.domain.errors import ConflictError
from tests.helpers import make_organization, make_organization_member, make_user


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


class TestCreateOrganizationUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        mock_repo = mocker.AsyncMock()
        mock_repo.get_by_slug.return_value = None
        mock_repo.save.return_value = make_organization(name="TestOrg", slug="test-org")

        mock_outbox = mocker.AsyncMock()

        uc = CreateOrganizationUseCase(org_repo=mock_repo, outbox=mock_outbox)
        result = await uc.execute(CreateOrganizationInput(name="TestOrg", slug="test-org"))

        assert result.name == "TestOrg"
        assert result.slug == "test-org"
        mock_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_duplicate_slug(self, mocker):
        mock_repo = mocker.AsyncMock()
        mock_repo.get_by_slug.return_value = make_organization(slug="dup-slug")

        uc = CreateOrganizationUseCase(org_repo=mock_repo, outbox=mocker.AsyncMock())
        with pytest.raises(ConflictError):
            await uc.execute(CreateOrganizationInput(name="TestOrg", slug="dup-slug"))
        mock_repo.save.assert_not_called()


class TestAddMemberToOrganizationUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        org_id = uuid6.uuid7()
        user_id = uuid6.uuid7()

        mock_org_repo = mocker.AsyncMock()
        mock_org_repo.get_by_id.return_value = make_organization()

        mock_user_repo = mocker.AsyncMock()
        mock_user_repo.get_by_id.return_value = make_user()

        mock_member_repo = mocker.AsyncMock()
        mock_member_repo.get_by_organization_and_user.return_value = None
        mock_member_repo.save.return_value = make_organization_member(
            user_id=user_id, organization_id=org_id, role=MemberRole.member
        )

        mock_outbox = mocker.AsyncMock()

        uc = AddMemberToOrganizationUseCase(
            org_repo=mock_org_repo,
            user_repo=mock_user_repo,
            member_repo=mock_member_repo,
            outbox=mock_outbox,
        )
        result = await uc.execute(
            AddMemberInput(user_id=user_id, organization_id=org_id)
        )

        assert result.role == MemberRole.member
        mock_member_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_organization_not_found(self, mocker):
        mock_org_repo = mocker.AsyncMock()
        mock_org_repo.get_by_id.return_value = None

        uc = AddMemberToOrganizationUseCase(
            org_repo=mock_org_repo,
            user_repo=mocker.AsyncMock(),
            member_repo=mocker.AsyncMock(),
            outbox=mocker.AsyncMock(),
        )
        with pytest.raises(OrganizationNotFoundError):
            await uc.execute(
                AddMemberInput(
                    user_id=uuid6.uuid7(),
                    organization_id=uuid6.uuid7(),
                )
            )

    @pytest.mark.asyncio
    async def test_user_not_found(self, mocker):
        mock_org_repo = mocker.AsyncMock()
        mock_org_repo.get_by_id.return_value = make_organization()

        mock_user_repo = mocker.AsyncMock()
        mock_user_repo.get_by_id.return_value = None

        uc = AddMemberToOrganizationUseCase(
            org_repo=mock_org_repo,
            user_repo=mock_user_repo,
            member_repo=mocker.AsyncMock(),
            outbox=mocker.AsyncMock(),
        )
        with pytest.raises(UserNotFoundError):
            await uc.execute(
                AddMemberInput(
                    user_id=uuid6.uuid7(),
                    organization_id=uuid6.uuid7(),
                )
            )

    @pytest.mark.asyncio
    async def test_already_member(self, mocker):
        org_id = uuid6.uuid7()
        user_id = uuid6.uuid7()

        mock_org_repo = mocker.AsyncMock()
        mock_org_repo.get_by_id.return_value = make_organization()

        mock_user_repo = mocker.AsyncMock()
        mock_user_repo.get_by_id.return_value = make_user()

        mock_member_repo = mocker.AsyncMock()
        mock_member_repo.get_by_organization_and_user.return_value = make_organization_member()

        uc = AddMemberToOrganizationUseCase(
            org_repo=mock_org_repo,
            user_repo=mock_user_repo,
            member_repo=mock_member_repo,
            outbox=mocker.AsyncMock(),
        )
        with pytest.raises(ConflictError):
            await uc.execute(
                AddMemberInput(user_id=user_id, organization_id=org_id)
            )
        mock_member_repo.save.assert_not_called()


class TestInviteUserUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        org_id = uuid6.uuid7()

        mock_org_repo = mocker.AsyncMock()
        mock_org_repo.get_by_id.return_value = make_organization()

        mock_invite_repo = mocker.AsyncMock()
        mock_invite_repo.get_by_organization_and_email.return_value = None

        saved_invite = OrganizationInvite(
            id=uuid6.uuid7(),
            organization_id=org_id,
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
            org_repo=mock_org_repo,
            invite_repo=mock_invite_repo,
            outbox=mock_outbox,
        )
        result = await uc.execute(
            InviteUserInput(
                organization_id=org_id,
                email="invite@test.com",
                invited_by_user_id=uuid6.uuid7(),
            )
        )

        assert result.email == "invite@test.com"
        assert result.status == InviteStatus.pending
        mock_invite_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_organization_not_found(self, mocker):
        mock_org_repo = mocker.AsyncMock()
        mock_org_repo.get_by_id.return_value = None

        uc = InviteUserUseCase(
            org_repo=mock_org_repo,
            invite_repo=mocker.AsyncMock(),
            outbox=mocker.AsyncMock(),
        )
        with pytest.raises(OrganizationNotFoundError):
            await uc.execute(
                InviteUserInput(
                    organization_id=uuid6.uuid7(),
                    email="invite@test.com",
                    invited_by_user_id=uuid6.uuid7(),
                )
            )

    @pytest.mark.asyncio
    async def test_pending_invite_exists(self, mocker):
        org_id = uuid6.uuid7()

        mock_org_repo = mocker.AsyncMock()
        mock_org_repo.get_by_id.return_value = make_organization()

        existing_invite = OrganizationInvite(
            email="invite@test.com",
            organization_id=org_id,
            status=InviteStatus.pending,
        )
        mock_invite_repo = mocker.AsyncMock()
        mock_invite_repo.get_by_organization_and_email.return_value = existing_invite

        uc = InviteUserUseCase(
            org_repo=mock_org_repo,
            invite_repo=mock_invite_repo,
            outbox=mocker.AsyncMock(),
        )
        with pytest.raises(ConflictError):
            await uc.execute(
                InviteUserInput(
                    organization_id=org_id,
                    email="invite@test.com",
                    invited_by_user_id=uuid6.uuid7(),
                )
            )
        mock_invite_repo.save.assert_not_called()
