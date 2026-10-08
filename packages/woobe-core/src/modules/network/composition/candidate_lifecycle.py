from modules.network.composition.resources import SESSION_FACTORY
from modules.network.composition.services import build_network_service
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.infra.services.development_resource_reader import DevelopmentNetworkReader
from modules.network.infra.services.candidate_lifecycle import NetworkCandidateLifecycleHandler
from shared.infra.transactional_handler import TransactionalHandler


def network_candidate_lifecycle_composer():
    uow = NetworkUnitOfWork(SESSION_FACTORY.kw["bind"])
    handler = NetworkCandidateLifecycleHandler(uow, DevelopmentNetworkReader(), build_network_service())
    return TransactionalHandler(uow, handler.handle)
