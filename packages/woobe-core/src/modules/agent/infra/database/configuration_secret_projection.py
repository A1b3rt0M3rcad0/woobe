"""Owner-scoped, metadata-only compilation of retained Secret header templates."""
from copy import deepcopy
from sqlalchemy import select
from modules.agent.domain.legacy_tool_configuration import bind_legacy_tool_headers, legacy_tool_secret_names
from modules.agent.infra.database.models import AgentToolSecretModel


async def project_secret_headers(session, *, project_id, tools, portable=False):
    names = set().union(*(legacy_tool_secret_names(tool.config or {}) for tool in tools)) if tools else set()
    if not names:
        return [_portable(tool) for tool in tools] if portable else tools
    rows = (await session.execute(select(AgentToolSecretModel.name, AgentToolSecretModel.configuration_reference).where(
        AgentToolSecretModel.project_id == project_id, AgentToolSecretModel.name.in_(names),
        AgentToolSecretModel.configuration_reference.is_not(None)))).all()
    references = {row.name: row.configuration_reference for row in rows}
    projected = [bind_legacy_tool_headers(tool, references) for tool in tools]
    return [_portable(tool) for tool in projected] if portable else projected


def _portable(tool):
    result = deepcopy(tool)
    authentication = (result.config or {}).get("authentication")
    if authentication:
        for field, reference in authentication.get("fields", {}).items():
            if reference.get("source") == "legacy_configuration":
                authentication["fields"][field] = {"source": "project_environment", "key": reference["key"]}
    return result
