from modules.agent.composition.factories.agent_uow_factory import build_agent_uow
from modules.agent.infra.database.chat_surface_target_release_reader import (
    AgentChatSurfaceTargetReleaseReader,
)


def build_agent_chat_surface_target_release_reader() -> AgentChatSurfaceTargetReleaseReader:
    return AgentChatSurfaceTargetReleaseReader(build_agent_uow())


__all__ = ["build_agent_chat_surface_target_release_reader"]
