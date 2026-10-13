"""Invocation-local references, resolved immediately before the HTTP send."""
from base64 import b64encode
from functools import wraps

from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.interfaces.project_configuration import resolve_runtime_configuration, current_tool_configuration
from modules.agent.domain.tool_configuration import tool_authentication
from shared.contracts.project_configuration import ConfigurationError



def configuration_bound_tool(function):
    @wraps(function)
    async def execute(self, tool, *args, **kwargs):
        auth = tool_authentication(getattr(tool, "config", None) or {})
        if auth is None or not auth["fields"]:
            return await function(self, tool, *args, **kwargs)
        context = current_execution.get()
        if context is None or context.run_id is None or context.project_id != tool.project_id:
            raise ConfigurationError("CONFIG_USAGE_NOT_AUTHORIZED")
        token = current_tool_configuration.set((tool.project_id, context.network_execution_id or context.run_id, tool.id, auth))
        try:
            return await function(self, tool, *args, **kwargs)
        finally:
            current_tool_configuration.reset(token)
    return execute


class PrivateHeaders(dict):
    def __init__(self, headers, values):
        super().__init__(headers)
        self.fragments = tuple(sorted(set([*headers.values(), *values]), key=len, reverse=True))

    def __repr__(self):
        return "<private configuration headers>"

    def scrub(self, value):
        if isinstance(value, str):
            for fragment in self.fragments:
                value = value.replace(fragment, "[REDACTED]")
            return value
        if isinstance(value, list):
            return [self.scrub(item) for item in value]
        if isinstance(value, dict):
            return {self.scrub(key): self.scrub(item) for key, item in value.items()}
        return value

    def clear(self):
        self.fragments = ()
        super().clear()


async def configuration_headers(destination):
    binding = current_tool_configuration.get()
    if binding is None:
        return {}
    project_id, run_id, tool_id, auth = binding
    values = {}
    for field in auth["fields"]:
        value = await resolve_runtime_configuration(project_id=project_id, run_id=run_id,
            consumer_kind="tool", consumer_id=tool_id,
            field_path="/config/authentication/fields/" + field, destination=destination)
        if not isinstance(value, str) or not value or any(c in value for c in "\r\n\x00"):
            raise ConfigurationError("CONFIG_VALUE_INVALID")
        values[field] = value
    if auth["type"] == "headers":
        return PrivateHeaders(values, values.values())
    if auth["type"] == "basic":
        if ":" in values["username"]:
            raise ConfigurationError("CONFIG_VALUE_INVALID")
        encoded = b64encode((values["username"] + ":" + values["password"]).encode()).decode()
        return PrivateHeaders({"Authorization": "Basic " + encoded}, values.values())
    if auth["type"] == "bearer":
        return PrivateHeaders({"Authorization": "Bearer " + values["token"]}, values.values())
    return PrivateHeaders({"X-API-Key": values["api_key"]}, values.values())
