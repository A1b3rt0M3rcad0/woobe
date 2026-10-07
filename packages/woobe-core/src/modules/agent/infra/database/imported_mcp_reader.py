from copy import deepcopy
import re

from modules.agent.application.interfaces.imported_mcp import PreparedMcpInputs
from modules.agent.application.interfaces.ports import ToolSecretResolverPort
from modules.agent.domain.tool_project_environment import (
    collect_tool_project_environment_keys,
)
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.database.models import AgentToolSecretModel
from modules.agent.infra.database.repositories import SQLAlchemyAgentToolRepository
from shared.contracts.errors import AuthorizationError, NotFoundError
from shared.project_environment import (
    read_project_environment_values,
    materialize_project_environment_values,
)
from shared.security.principal import ControlPlanePrincipal, AuthenticatedPrincipal
from shared.security.tenancy import TenantAuthorizer
from sqlalchemy import select

_SECRET = re.compile(r"\{\{secret:([^}]+)\}\}")


class PreparedMcpSecretResolver(ToolSecretResolverPort):
    def __init__(self, secrets, cipher):
        self._secrets, self._cipher = secrets, cipher

    async def resolve_headers(self, headers, project_id):
        result = {}
        for header in headers:
            value = header.get("value", "")
            for match in list(_SECRET.finditer(value)):
                name = match[1].strip()
                if name not in self._secrets:
                    raise NotFoundError("Imported MCP Secret is unavailable")
                value = value.replace(
                    match[0], await self._cipher.decrypt(self._secrets[name])
                )
            result[header["key"]] = value
        return result


class SQLAlchemyImportedMcpPreparationReader:
    def __init__(self, uow_factory, *, encryption_key):
        self._uow_factory, self._encryption_key = uow_factory, encryption_key

    async def read(self, *, project_id, principal, tool_id):
        async with self._uow_factory() as uow:
            authorizer = TenantAuthorizer(uow.session)
            if isinstance(principal, ControlPlanePrincipal):
                await authorizer.require_active_control(principal)
                await authorizer.authorize_control_key(
                    api_key_id=principal.api_key_id,
                    workspace_id=principal.workspace_id,
                    workspace_permissions=principal.permissions,
                    required_permission="tool:write",
                    path_params={
                        "project_id": str(project_id),
                        "tool_id": str(tool_id),
                    },
                    body={"tool_id": str(tool_id)},
                    query_params={},
                )
            elif isinstance(principal, AuthenticatedPrincipal):
                await authorizer.require_active_human(principal)
                workspace = await authorizer._project_workspace_id(project_id)
                await authorizer.require_human_permission(
                    user_id=principal.user_id,
                    workspace_id=workspace,
                    project_id=project_id,
                    permission="tool:write",
                    path_context={
                        "project_id": str(project_id),
                        "tool_id": str(tool_id),
                    },
                )
            else:
                raise AuthorizationError("Administrative authentication is required")
            tool = await SQLAlchemyAgentToolRepository(uow).get_by_id(tool_id)
            if tool.project_id != project_id:
                raise NotFoundError("Imported MCP Tool is unavailable")
            raw = deepcopy(tool.config)
            names = {match[1].strip() for match in _SECRET.finditer(str(raw))}
            secrets = {}
            if names:
                rows = await uow.session.execute(
                    select(
                        AgentToolSecretModel.name, AgentToolSecretModel.encrypted_value
                    ).where(
                        AgentToolSecretModel.project_id == project_id,
                        AgentToolSecretModel.name.in_(names),
                    )
                )
                secrets = dict(rows.all())
                if set(secrets) != names:
                    raise NotFoundError("Imported MCP Secrets are unavailable")
            environment = await read_project_environment_values(
                uow.session,
                project_id=project_id,
                environment="draft",
                keys=collect_tool_project_environment_keys(raw),
            )
            revision = tool.updated_at.isoformat()

        # Only detached identities/encrypted references leave the short read scope.
        async def resolve_environment(*, project_id, environment, keys):
            return materialize_project_environment_values(
                prepared_environment, encryption_key=self._encryption_key
            )

        prepared_environment = environment
        return PreparedMcpInputs(
            tool,
            revision,
            PreparedMcpSecretResolver(
                secrets, SecretCipherAdapter(self._encryption_key)
            ),
            resolve_environment,
        )
