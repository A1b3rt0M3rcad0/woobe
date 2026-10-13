from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.database.vector_preparation import PrepareVectorSnapshot
from shared.infra.transactional_handler import TransactionalHandler


def _permissions(request):
    return [("knowledge:write", None), ("project:environment:validate", None)]


def prepare_vector_snapshot_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    controller = PrepareVectorSnapshot(uow)
    return TransactionalHandler(uow, controller, additional_permissions=_permissions)
