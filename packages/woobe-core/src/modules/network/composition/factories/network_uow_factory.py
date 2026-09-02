from modules.network.composition.resources import DATABASE_ENGINE
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork


def build_network_read_uow() -> NetworkUnitOfWork:
    """Short SQL read scope that always ends with rollback, never COMMIT."""

    return NetworkUnitOfWork(DATABASE_ENGINE).mark_read_only()
