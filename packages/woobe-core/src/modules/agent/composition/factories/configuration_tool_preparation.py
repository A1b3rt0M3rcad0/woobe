from modules.agent.application.mcp_tool_bootstrap import McpToolBootstrapper
from modules.agent.composition.factories.agent_uow_factory import build_agent_uow
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.configuration_tool_preparation import ConfigurationToolPreparation


def build_configuration_tool_preparation():
    return ConfigurationToolPreparation(build_agent_uow, McpToolBootstrapper(get_http_tool_executor()))
