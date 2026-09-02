from uuid import UUID

from modules.identity.application.dtos import UpdateWorkspaceInput, UpdateWorkspaceOutput
from modules.identity.application.interfaces.outbox import OutboxEventWriter
from modules.identity.application.interfaces.repositories import WorkspaceRepository
from modules.identity.application.interfaces.workspace_access import WorkspaceAccessRepository
from modules.identity.domain.errors import WorkspaceNotFoundError
from shared.contracts.errors import ConflictError
from shared.contracts.time import utc_now


class UpdateWorkspaceAsAdminUseCase:
    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        access_repo: WorkspaceAccessRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._workspace_repo = workspace_repo
        self._access_repo = access_repo
        self._outbox = outbox

    async def execute(
        self,
        actor_user_id: UUID,
        workspace_id: UUID,
        input_dto: UpdateWorkspaceInput,
    ) -> UpdateWorkspaceOutput:
        await self._access_repo.require_admin(actor_user_id, workspace_id)
        workspace = await self._workspace_repo.get_by_id(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError(workspace_id)

        if input_dto.name is not None:
            workspace.name = input_dto.name
        if input_dto.slug is not None:
            existing = await self._workspace_repo.get_by_slug(input_dto.slug)
            if existing and existing.id != workspace_id:
                raise ConflictError(
                    f"Workspace with slug '{input_dto.slug}' already exists"
                )
            workspace.slug = input_dto.slug

        workspace.updated_at = utc_now()
        saved = await self._workspace_repo.save(workspace)
        await self._outbox.write(
            aggregate_type="workspace",
            aggregate_id=saved.id,
            event_type="workspace.updated.v1",
            payload={"name": saved.name, "slug": saved.slug},
            routing_key="workspace.updated.v1",
            idempotency_key=f"identity:workspace.updated.v1:{saved.id}",
        )
        return UpdateWorkspaceOutput(
            id=saved.id,
            name=saved.name,
            slug=saved.slug,
            status=saved.status,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )


class ListWorkspaceMembersAccessUseCase:
    def __init__(self, access_repo: WorkspaceAccessRepository) -> None:
        self._access_repo = access_repo

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
    ) -> list[dict[str, object]]:
        return await self._access_repo.list_members(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
        )


class RemoveWorkspaceMemberUseCase:
    def __init__(self, access_repo: WorkspaceAccessRepository) -> None:
        self._access_repo = access_repo

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        target_user_id: UUID,
    ) -> dict[str, object]:
        return await self._access_repo.remove_member(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            target_user_id=target_user_id,
        )


class ListWorkspaceInvitesAccessUseCase:
    def __init__(self, access_repo: WorkspaceAccessRepository) -> None:
        self._access_repo = access_repo

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
    ) -> list[dict[str, object]]:
        return await self._access_repo.list_invites(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
        )


class CancelWorkspaceInviteUseCase:
    def __init__(self, access_repo: WorkspaceAccessRepository) -> None:
        self._access_repo = access_repo

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        invite_id: UUID,
    ) -> dict[str, object]:
        return await self._access_repo.cancel_invite(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            invite_id=invite_id,
        )
