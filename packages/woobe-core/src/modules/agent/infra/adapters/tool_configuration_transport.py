"""Invocation-local references, resolved immediately before the HTTP send."""
from base64 import b64encode, b64decode
from functools import wraps

from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.interfaces.project_configuration import resolve_runtime_configuration, current_tool_configuration
from modules.agent.domain.tool_configuration import invocation_authentication
from modules.agent.application.interfaces.tool_runtime import MCP_REMOTE_TOOL_INPUT_KEY
from shared.contracts.project_configuration import ConfigurationError



def configuration_bound_tool(function):
    @wraps(function)
    async def execute(self, tool, *args, **kwargs):
        input_data = args[0] if args else kwargs.get('input_data')
        route_id = (input_data or {}).get(MCP_REMOTE_TOOL_INPUT_KEY)
        auth = invocation_authentication(getattr(tool, "config", None) or {}, route_id)
        if auth is None or (not auth["fields"] and not auth.get('bindings')):
            token = current_tool_configuration.set(None)
            try:
                return await function(self, tool, *args, **kwargs)
            finally:
                current_tool_configuration.reset(token)
        prepared = current_tool_configuration.get()
        if prepared is not None:
            # A persisted Tool can also be invoked by an explicitly authorized
            # administrative operation. Its central lease is checked per send;
            # never reuse an enclosing operation for a different Tool/binding.
            if prepared[0] != tool.project_id or prepared[2] != tool.id or prepared[3] != auth:
                raise ConfigurationError("CONFIG_USAGE_NOT_AUTHORIZED")
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
        fragments = [*headers.values(), *values]
        for name, value in headers.items():
            if name.lower() == 'authorization' and ' ' in value:
                scheme, material = value.split(' ', 1)
                fragments.append(material)
                if scheme.lower() == 'basic':
                    try:
                        decoded = b64decode(material, validate=True).decode('utf-8')
                        fragments.extend([decoded, *decoded.split(':', 1)])
                    except (ValueError, UnicodeError):
                        pass
            if name.lower() == 'cookie':
                fragments.extend(pair.split('=', 1)[1].strip() for pair in value.split(';') if '=' in pair)
        self.fragments = tuple(sorted({fragment for fragment in fragments if fragment}, key=len, reverse=True))

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
    if auth['type'] == 'composite':
        headers, fragments = {}, []
        for scoped in auth['bindings']:
            resolved = await _authentication_headers(project_id, run_id, tool_id,
                scoped['authentication'], scoped['field_prefix'], destination)
            fragments.extend(resolved.fragments)
            for name, value in resolved.items():
                previous = next((key for key in headers if key.lower() == name.lower()), None)
                if previous is not None:
                    del headers[previous]
                headers[name] = value
            resolved.clear()
        return PrivateHeaders(headers, fragments)
    return await _authentication_headers(project_id, run_id, tool_id, auth,
        '/config/authentication/fields/', destination)


async def _authentication_headers(project_id, run_id, tool_id, auth, prefix, destination):
    values = {}
    for field in auth["fields"]:
        value = await resolve_runtime_configuration(project_id=project_id, run_id=run_id,
            consumer_kind="tool", consumer_id=tool_id,
            field_path=prefix + field, destination=destination)
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
