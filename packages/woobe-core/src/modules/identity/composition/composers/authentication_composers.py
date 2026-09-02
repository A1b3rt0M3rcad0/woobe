from modules.identity.application.use_cases import (
    AcceptWorkspaceInviteUseCase,
    CreateOwnedWorkspaceUseCase,
    CreateWorkspaceInviteUseCase,
    GetAuthenticatedUserUseCase,
    ListAuthenticatedWorkspacesUseCase,
    ListPendingWorkspaceInvitesUseCase,
    LoginAuthenticationUseCase,
    LogoutAuthenticationUseCase,
    RefreshAuthenticationUseCase,
    RegisterAuthenticationUseCase,
)
from modules.identity.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.identity.infra.database.authentication_repositories import (
    SQLAlchemyAuthenticationRepository,
    SQLAlchemyAuthenticationSessionRepository,
)
from modules.identity.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyUserRepository,
    SQLAlchemyWorkspaceMemberRepository,
    SQLAlchemyWorkspaceRepository,
)
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.infra.database.workspace_access_repository import SQLAlchemyWorkspaceAccessRepository
from modules.identity.presentation.authentication_response import AuthenticationCookiePolicy
from modules.identity.presentation.controllers.authentication_controllers import (
    AcceptWorkspaceInviteController,
    CreateOwnedWorkspaceController,
    CreateWorkspaceInviteController,
    CsrfController,
    GetAuthenticatedUserController,
    ListAuthenticatedWorkspacesController,
    ListPendingWorkspaceInvitesController,
    LoginAuthenticationController,
    LogoutAuthenticationController,
    RefreshAuthenticationController,
    RegisterAuthenticationController,
)
from shared.infra.transactional_handler import TransactionalHandler
from shared.security.access_tokens import AccessTokenCodec


def _cookie_policy() -> AuthenticationCookiePolicy:
    return AuthenticationCookiePolicy(
        access_cookie_name=SETTINGS.access_cookie_name,
        access_cookie_secure=SETTINGS.access_cookie_secure,
        access_cookie_same_site=SETTINGS.access_cookie_same_site,
        refresh_cookie_name=SETTINGS.refresh_cookie_name,
        refresh_cookie_secure=SETTINGS.refresh_cookie_secure,
        refresh_cookie_same_site=SETTINGS.refresh_cookie_same_site,
        csrf_cookie_name=SETTINGS.csrf_cookie_name,
        refresh_token_ttl_days=SETTINGS.refresh_token_ttl_days,
        access_token_ttl_seconds=SETTINGS.access_token_ttl_seconds,
    )


def _token_issuer() -> AccessTokenCodec:
    return AccessTokenCodec(
        signing_key=SETTINGS.secret_key,
        issuer=SETTINGS.auth_issuer,
        audience=SETTINGS.auth_audience,
        ttl_seconds=SETTINGS.access_token_ttl_seconds,
        leeway_seconds=SETTINGS.auth_clock_skew_seconds,
    )


def login_authentication_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    user_repo = SQLAlchemyUserRepository(uow)
    session_repo = SQLAlchemyAuthenticationSessionRepository(uow, ttl_days=SETTINGS.refresh_token_ttl_days)
    token_issuer = _token_issuer()
    use_case = LoginAuthenticationUseCase(user_repo, session_repo, token_issuer)
    controller = LoginAuthenticationController(use_case, _cookie_policy())
    return TransactionalHandler(uow, controller.handle)


def register_authentication_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    user_repo = SQLAlchemyUserRepository(uow)
    workspace_repo = SQLAlchemyWorkspaceRepository(uow)
    member_repo = SQLAlchemyWorkspaceMemberRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    session_repo = SQLAlchemyAuthenticationSessionRepository(uow, ttl_days=SETTINGS.refresh_token_ttl_days)
    token_issuer = _token_issuer()
    use_case = RegisterAuthenticationUseCase(user_repo, workspace_repo, member_repo, outbox, session_repo, token_issuer)
    controller = RegisterAuthenticationController(use_case, _cookie_policy())
    return TransactionalHandler(uow, controller.handle)


def refresh_authentication_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    user_repo = SQLAlchemyUserRepository(uow)
    session_repo = SQLAlchemyAuthenticationSessionRepository(uow, ttl_days=SETTINGS.refresh_token_ttl_days)
    token_issuer = _token_issuer()
    use_case = RefreshAuthenticationUseCase(user_repo, session_repo, token_issuer)
    controller = RefreshAuthenticationController(use_case, _cookie_policy())
    return TransactionalHandler(uow, controller.handle)


def logout_authentication_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    session_repo = SQLAlchemyAuthenticationSessionRepository(uow, ttl_days=SETTINGS.refresh_token_ttl_days)
    use_case = LogoutAuthenticationUseCase(session_repo)
    controller = LogoutAuthenticationController(use_case, _cookie_policy())
    return TransactionalHandler(uow, controller.handle)


def get_authenticated_user_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    user_repo = SQLAlchemyUserRepository(uow)
    use_case = GetAuthenticatedUserUseCase(user_repo)
    controller = GetAuthenticatedUserController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_authenticated_workspaces_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    auth_repo = SQLAlchemyAuthenticationRepository(uow)
    use_case = ListAuthenticatedWorkspacesUseCase(auth_repo)
    controller = ListAuthenticatedWorkspacesController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_pending_workspace_invites_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    user_repo = SQLAlchemyUserRepository(uow)
    auth_repo = SQLAlchemyAuthenticationRepository(uow)
    use_case = ListPendingWorkspaceInvitesUseCase(user_repo, auth_repo)
    controller = ListPendingWorkspaceInvitesController(use_case)
    return TransactionalHandler(uow, controller.handle)


def create_owned_workspace_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    user_repo = SQLAlchemyUserRepository(uow)
    workspace_repo = SQLAlchemyWorkspaceRepository(uow)
    member_repo = SQLAlchemyWorkspaceMemberRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateOwnedWorkspaceUseCase(user_repo, workspace_repo, member_repo, outbox)
    controller = CreateOwnedWorkspaceController(use_case)
    return TransactionalHandler(uow, controller.handle)


def create_workspace_invite_authentication_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    workspace_repo = SQLAlchemyWorkspaceRepository(uow)
    auth_repo = SQLAlchemyAuthenticationRepository(uow)
    access_repo = SQLAlchemyWorkspaceAccessRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateWorkspaceInviteUseCase(workspace_repo, auth_repo, access_repo, outbox)
    controller = CreateWorkspaceInviteController(use_case)
    return TransactionalHandler(uow, controller.handle)


def accept_workspace_invite_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    user_repo = SQLAlchemyUserRepository(uow)
    auth_repo = SQLAlchemyAuthenticationRepository(uow)
    access_repo = SQLAlchemyWorkspaceAccessRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = AcceptWorkspaceInviteUseCase(user_repo, auth_repo, access_repo, outbox)
    controller = AcceptWorkspaceInviteController(use_case)
    return TransactionalHandler(uow, controller.handle)


def csrf_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    controller = CsrfController(_cookie_policy())
    return TransactionalHandler(uow, controller.handle)
