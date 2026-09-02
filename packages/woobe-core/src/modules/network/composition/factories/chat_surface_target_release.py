from modules.network.composition.resources import DATABASE_ENGINE
from modules.network.infra.database.chat_surface_target_release_reader import (
    NetworkChatSurfaceTargetReleaseReader,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork


def build_network_chat_surface_target_release_reader() -> NetworkChatSurfaceTargetReleaseReader:
    return NetworkChatSurfaceTargetReleaseReader(NetworkUnitOfWork(DATABASE_ENGINE))


__all__ = ["build_network_chat_surface_target_release_reader"]
