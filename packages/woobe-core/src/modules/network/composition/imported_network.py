from modules.network.composition.resources import SESSION_FACTORY
from modules.network.composition.services import build_network_service
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.infra.services.imported_network import ImportedNetworkHandler
from shared.infra.transactional_handler import TransactionalHandler


def imported_network_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(SESSION_FACTORY.kw["bind"])
    return TransactionalHandler(
        uow, ImportedNetworkHandler(uow, build_network_service()).handle
    )
