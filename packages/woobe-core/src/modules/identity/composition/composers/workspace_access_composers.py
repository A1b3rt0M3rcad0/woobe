from modules.identity.application.use_cases import (
    CancelWorkspaceInviteUseCase,
    ListWorkspaceInvitesAccessUseCase,
    ListWorkspaceMembersAccessUseCase,
    RemoveWorkspaceMemberUseCase,
    RequireWorkspaceRoleAssignmentUseCase,
    ValidateWorkspaceInviteAcceptanceUseCase,
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
    RequireWorkspaceRoleAssignmentController,
    ValidateWorkspaceInviteAcceptanceController,
)
from shared.infra.transactional_handler import TransactionalHandler


def require_workspace_role_assignment_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    access_repo = SQLAlchemyWorkspaceAccessRepository(uow)
    use_case = RequireWorkspaceRoleAssignmentUseCase(access_repo)
    controller = RequireWorkspaceRoleAssignmentController(use_case)
    return TransactionalHandler(uow, controller.handle)


def validate_workspace_invite_acceptance_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    access_repo = SQLAlchemyWorkspaceAccessRepository(uow)
    use_case = ValidateWorkspaceInviteAcceptanceUseCase(access_repo)
    controller = ValidateWorkspaceInviteAcceptanceController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_workspace_members_access_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    access_repo = SQLAlchemyWorkspaceAccessRepository(uow)
    use_case = ListWorkspaceMembersAccessUseCase(access_repo)
    controller = ListWorkspaceMembersAccessController(use_case)
    return TransactionalHandler(uow, controller.handle)


def remove_workspace_member_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    access_repo = SQLAlchemyWorkspaceAccessRepository(uow)
    use_case = RemoveWorkspaceMemberUseCase(access_repo)
    controller = RemoveWorkspaceMemberController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_workspace_invites_access_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    access_repo = SQLAlchemyWorkspaceAccessRepository(uow)
    use_case = ListWorkspaceInvitesAccessUseCase(access_repo)
    controller = ListWorkspaceInvitesAccessController(use_case)
    return TransactionalHandler(uow, controller.handle)


def cancel_workspace_invite_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    access_repo = SQLAlchemyWorkspaceAccessRepository(uow)
    use_case = CancelWorkspaceInviteUseCase(access_repo)
    controller = CancelWorkspaceInviteController(use_case)
    return TransactionalHandler(uow, controller.handle)
