from modules.identity.application.use_cases import (
    CancelWorkspaceInviteUseCase,
    ListWorkspaceInvitesAccessUseCase,
    ListWorkspaceMembersAccessUseCase,
    RemoveWorkspaceMemberUseCase,
)
from modules.identity.composition.resources import DATABASE_ENGINE
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.infra.database.workspace_access_repository import (
    SQLAlchemyWorkspaceAccessRepository,
)
from modules.identity.presentation.controllers.workspace_access_controllers import (
    CancelWorkspaceInviteController,
    ListWorkspaceInvitesAccessController,
    ListWorkspaceMembersAccessController,
    RemoveWorkspaceMemberController,
)
from shared.infra.transactional_handler import TransactionalHandler


def list_workspace_members_access_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    use_case = ListWorkspaceMembersAccessUseCase(
        SQLAlchemyWorkspaceAccessRepository(uow)
    )
    controller = ListWorkspaceMembersAccessController(use_case)
    return TransactionalHandler(uow, controller.handle)


def remove_workspace_member_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    use_case = RemoveWorkspaceMemberUseCase(SQLAlchemyWorkspaceAccessRepository(uow))
    controller = RemoveWorkspaceMemberController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_workspace_invites_access_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    use_case = ListWorkspaceInvitesAccessUseCase(
        SQLAlchemyWorkspaceAccessRepository(uow)
    )
    controller = ListWorkspaceInvitesAccessController(use_case)
    return TransactionalHandler(uow, controller.handle)


def cancel_workspace_invite_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    use_case = CancelWorkspaceInviteUseCase(SQLAlchemyWorkspaceAccessRepository(uow))
    controller = CancelWorkspaceInviteController(use_case)
    return TransactionalHandler(uow, controller.handle)
