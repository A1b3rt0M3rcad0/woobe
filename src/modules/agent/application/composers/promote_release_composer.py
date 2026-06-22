from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseRepository
from modules.agent.application.use_cases.auto_compatible_release_lifecycle import AutoCompatibleReleaseLifecycleUseCase
from modules.agent.presentation.controllers.promote_release_controller import PromoteReleaseController
from shared.presentation.http.response import Response
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


class _PromoteReleaseController(PromoteReleaseController):
    async def handle(self, request):
        response = await super().handle(request)
        if isinstance(response, Response) and isinstance(response.body, dict):
            response.body.setdefault("meta", {})["lifecycle_use_case"] = "AutoCompatibleReleaseLifecycleUseCase"
        return response


def promote_release_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = SQLAlchemyAgentReleaseRepository(uow)
    use_case = AutoCompatibleReleaseLifecycleUseCase(repo)
    controller = _PromoteReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
