from modules.agent.composition.factories.ask_agent_runtime_factory import (
    build_ask_agent_handler,
)
from modules.agent.composition.resources import SETTINGS
from shared.infra.workflow_handler import WorkflowHandler


def ask_agent_composer() -> WorkflowHandler:
    handler = build_ask_agent_handler(SETTINGS)
    return WorkflowHandler(handler)
