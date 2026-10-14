"""Keep OAuth protocol material inside its owner flow, outside Tool results."""
from modules.agent.application.interfaces.oauth_protocol import private_oauth_protocol_response
from modules.agent.application.interfaces.project_configuration import current_tool_configuration


class OAuthProtocolExecutor:
    def __init__(self, executor):
        self.executor = executor

    async def execute(self, *args, **kwargs):
        private = private_oauth_protocol_response.set(True)
        parent = current_tool_configuration.set(None)
        try:
            return await self.executor.execute(*args, **kwargs)
        finally:
            current_tool_configuration.reset(parent)
            private_oauth_protocol_response.reset(private)
