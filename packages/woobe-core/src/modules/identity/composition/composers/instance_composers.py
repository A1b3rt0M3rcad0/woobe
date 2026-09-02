from modules.identity.application.use_cases import (
    BootstrapExistingOwnerUseCase,
    BootstrapInstanceUseCase,
    InstanceStatusUseCase,
)
from modules.identity.composition.factories.authentication import (
    build_access_token_issuer,
    build_authentication_cookie_policy,
)
from modules.identity.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.identity.infra.database.authentication_repositories import SQLAlchemyAuthenticationSessionRepository
from modules.identity.infra.database.instance_repository import SQLAlchemyInstanceRepository
from modules.identity.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyUserRepository,
    SQLAlchemyWorkspaceMemberRepository,
    SQLAlchemyWorkspaceRepository,
)
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.presentation.controllers.instance_controllers import (
    BootstrapExistingOwnerController,
    BootstrapInstanceController,
    InstanceStatusController,
)
from shared.infra.transactional_handler import TransactionalHandler


def instance_status_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    instance_repo = SQLAlchemyInstanceRepository(uow)
    use_case = InstanceStatusUseCase(instance_repo, edition=SETTINGS.edition)
    controller = InstanceStatusController(use_case)
    return TransactionalHandler(uow, controller.handle)


def bootstrap_instance_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    instance_repo = SQLAlchemyInstanceRepository(uow)
    user_repo = SQLAlchemyUserRepository(uow)
    workspace_repo = SQLAlchemyWorkspaceRepository(uow)
    member_repo = SQLAlchemyWorkspaceMemberRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    session_repo = SQLAlchemyAuthenticationSessionRepository(uow, ttl_days=SETTINGS.refresh_token_ttl_days)
    token_issuer = build_access_token_issuer()
    use_case = BootstrapInstanceUseCase(
        instance_repo,
        user_repo,
        workspace_repo,
        member_repo,
        outbox,
        session_repo,
        token_issuer,
        edition=SETTINGS.edition,
    )
    cookie_policy = build_authentication_cookie_policy()
    controller = BootstrapInstanceController(use_case, cookie_policy)
    return TransactionalHandler(uow, controller.handle)


def bootstrap_existing_owner_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    instance_repo = SQLAlchemyInstanceRepository(uow)
    use_case = BootstrapExistingOwnerUseCase(instance_repo, edition=SETTINGS.edition)
    controller = BootstrapExistingOwnerController(use_case)
    return TransactionalHandler(uow, controller.handle)
