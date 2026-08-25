from __future__ import annotations

from uuid import UUID

from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.interfaces.ports import ToolSecretResolverPort
from shared.contracts.errors import ValidationError

SECRET_REF_PREFIX = "{{secret:"
SECRET_REF_SUFFIX = "}}"


class RuntimeToolSecretResolver(ToolSecretResolverPort):
    """Resolve Tool secrets only from acceptance-time in-memory material."""

    async def resolve_headers(
        self,
        headers_config: list[dict],
        project_id: UUID,
    ) -> dict[str, str]:
        del project_id
        context = current_execution.get()
        prepared = context.prepared_tool_secrets if context else None
        resolved: dict[str, str] = {}
        for header in headers_config:
            key = str(header.get("key") or "")
            if not key:
                continue
            value = str(header.get("value") or "")
            if value.startswith(SECRET_REF_PREFIX):
                end = value.find(SECRET_REF_SUFFIX, len(SECRET_REF_PREFIX))
                if end != -1:
                    name = value[len(SECRET_REF_PREFIX):end].strip()
                    if not prepared or name not in prepared:
                        raise ValidationError(
                            f"Tool secret '{name}' was not prepared for this Run"
                        )
                    value = prepared[name]
            resolved[key] = value
        return resolved
