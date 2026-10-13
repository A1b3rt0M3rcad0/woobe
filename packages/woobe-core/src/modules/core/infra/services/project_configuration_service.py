"""Authorized transaction boundary for configuration administration."""
from uuid import UUID

from sqlalchemy import select

from modules.core.infra.database.configuration_resolution import ConfigurationResolution
from modules.core.infra.database.configuration_legacy import LegacyConfigurationStore
from modules.core.infra.database.models import ProjectModel
from shared.contracts.errors import AuthorizationError, NotFoundError
from shared.security.principal import AuthenticatedPrincipal, ControlPlanePrincipal
from shared.security.tenancy import TenantAuthorizer


_PERMISSIONS = {
    "migration_fleet": "migrate",
    "migration_preview": "migrate", "migration_create": "migrate", "migration_status": "migrate", "migration_advance": "migrate",
    "binding": "read", "bind": "bind",
    "legacy_bindings": "read", "convert": "migrate",
    "readiness": "read", "summary": "read",
    "list_use_policies": "read",
    "capabilities": "read",
    "list_keys": "read", "usage": "read", "declare": "declare", "patch": "declare",
    "remove_key": "declare", "write_value": "value:write", "write_batch": "value:write",
    "grant_use": "use-policy:write", "revoke_use": "use-policy:write",
}

_target_reader = None
_target_inventory = None
_binding_adapter = None
_migration_inventory = None
_migration_cutover = None
_migration_quiescence = None


def configure_configuration_migration_adapter(*, inventory, cutover, assert_quiescent):
    global _migration_inventory, _migration_cutover, _migration_quiescence
    _migration_inventory, _migration_cutover, _migration_quiescence = inventory, cutover, assert_quiescent

def configure_configuration_binding_adapter(adapter):
    global _binding_adapter
    _binding_adapter = adapter



def configure_configuration_target_reader(reader, *, inventory=None):
    global _target_reader, _target_inventory
    _target_reader, _target_inventory = reader, inventory


class ProjectConfigurationService:
    def __init__(self, session_factory, *, encryption_key):
        self.session_factory, self.encryption_key = session_factory, encryption_key

    async def execute(self, action, *, project_id: UUID, principal, **arguments):
        permission = _PERMISSIONS.get(action)
        if permission is None:
            raise AuthorizationError("Configuration operation is not authorized")
        if action == "write_value" and arguments.get("clear"):
            permission = "value:clear"
        async with self.session_factory() as session, session.begin():
            project = await session.scalar(select(ProjectModel).where(ProjectModel.id == project_id))
            if project is None:
                raise NotFoundError("Project not found")
            environments = arguments.get("environments") or [arguments.get("environment")]
            if action.startswith("migration_"):
                # Legacy source semantics span all three routes. A permission
                # restricted to Draft cannot authorize a cross-environment cutover.
                environments = ["draft", "staging", "production"]
            if action == "write_batch":
                environments = sorted({op["environment"] for op in arguments["operations"]})
            authorizer = TenantAuthorizer(session)
            if isinstance(principal, ControlPlanePrincipal):
                await authorizer.require_active_control(principal)
            elif isinstance(principal, AuthenticatedPrincipal):
                await authorizer.require_active_human(principal)
            for environment in environments:
                context = {"project_id": project_id}
                if environment is not None:
                    context["environment"] = environment
                permissions = [permission]
                if action == "convert":
                    permissions.append("value:write")
                if action == "write_batch" and any(op.get("clear") and op["environment"] == environment for op in arguments["operations"]):
                    permissions.append("value:clear")
                for operation in permissions:
                    required = "project:environment:" + operation
                    if isinstance(principal, ControlPlanePrincipal):
                        await authorizer.authorize_control_key(api_key_id=principal.api_key_id,
                            workspace_id=principal.workspace_id, workspace_permissions=principal.permissions,
                            required_permission=required, path_params=context, query_params={}, body=None)
                    elif isinstance(principal, AuthenticatedPrincipal):
                        await authorizer.require_human_permission(user_id=principal.user_id, workspace_id=project.workspace_id,
                            project_id=project_id, permission=required, path_context=context)
                    else:
                        raise AuthorizationError("Administrative authentication is required")
                if action.startswith("migration_"):
                    source_kind = arguments.get("source_kind", "provider_credential")
                    if arguments.get("migration_id"):
                        from modules.core.infra.database.configuration_models import ConfigurationMigrationModel
                        plan = await session.scalar(select(ConfigurationMigrationModel.plan).where(
                            ConfigurationMigrationModel.project_id == project_id,
                            ConfigurationMigrationModel.id == arguments["migration_id"]))
                        if plan:
                            source_kind = plan.get("request", {}).get("source_kind", "provider_credential")
                    source_permission = "secret" if source_kind == "secret" else "provider"
                    required = source_permission + (":write" if action == "migration_advance" else ":read")
                    if isinstance(principal, ControlPlanePrincipal):
                        await authorizer.authorize_control_key(api_key_id=principal.api_key_id,
                            workspace_id=principal.workspace_id, workspace_permissions=principal.permissions,
                            required_permission=required, path_params=context, query_params={}, body=None)
                    else:
                        await authorizer.require_human_permission(user_id=principal.user_id, workspace_id=project.workspace_id,
                            project_id=project_id, permission=required, path_context=context)
                if action in {"readiness", "binding", "bind"}:
                    required = {"agent": "agent:read", "network": "network:read", "provider_credential": "provider:read", "tool": "tool:read"}[arguments["target_kind"]]
                    if action == "bind":
                        required = required.replace(":read", ":write")
                    context["credential_id" if arguments["target_kind"] == "provider_credential" else arguments["target_kind"] + "_id"] = arguments["target_id"]
                    if isinstance(principal, ControlPlanePrincipal):
                        await authorizer.authorize_control_key(api_key_id=principal.api_key_id,
                            workspace_id=principal.workspace_id, workspace_permissions=principal.permissions,
                            required_permission=required, path_params=context, query_params={}, body=None)
                    else:
                        await authorizer.require_human_permission(user_id=principal.user_id, workspace_id=project.workspace_id,
                            project_id=project_id, permission=required, path_context=context)
            actor = "key:" + str(principal.api_key_id) if isinstance(principal, ControlPlanePrincipal) else "user:" + str(principal.user_id)
            if action.startswith("migration_"):
                from shared.contracts.project_configuration import ConfigurationError
                from modules.core.infra.services.configuration_migration import ConfigurationMigrationService
                if _migration_inventory is None or _migration_cutover is None or _migration_quiescence is None:
                    raise ConfigurationError("CONFIG_STORE_UNAVAILABLE")
                migration = ConfigurationMigrationService(session, encryption_key=self.encryption_key,
                    inventory=_migration_inventory, cutover=_migration_cutover, assert_quiescent=_migration_quiescence)
                operation = action.removeprefix("migration_")
                if operation in {"create", "advance"}:
                    arguments["actor"] = actor
                return await getattr(migration, operation)(project_id=project_id, **arguments)
            if action == "capabilities":
                return {"schema_version": "project_configuration.v1", "declaration_without_value": True,
                        "typed_remote_bindings": True, "binding_updates": _binding_adapter is not None, "external_validation": True, "metadata_only_reads": True,
                        "target_readiness": _target_reader is not None,
                        "project_summary": _target_inventory is not None,
                        "migration_source_kinds": ["provider_credential", "secret"] if _migration_inventory is not None else [],
                        "secret_reveal": False, "environment_fallback": False}
            if action in {"binding", "bind"}:
                from shared.contracts.project_configuration import ConfigurationError
                if _binding_adapter is None:
                    raise ConfigurationError("CONFIG_STORE_UNAVAILABLE")
                return await _binding_adapter(session, project_id=project_id, **arguments)
            if action == "summary":
                from modules.core.infra.services.configuration_summary import configuration_summary
                from shared.contracts.project_configuration import ConfigurationError
                if _target_reader is None or _target_inventory is None:
                    raise ConfigurationError("CONFIG_STORE_UNAVAILABLE")
                async def authorize_target(target):
                    required = target['kind'] + ':read'
                    context = {'project_id': project_id, 'environment': arguments['environment'],
                               target['kind'] + '_id': target['id']}
                    if isinstance(principal, ControlPlanePrincipal):
                        await authorizer.authorize_control_key(api_key_id=principal.api_key_id,
                            workspace_id=principal.workspace_id, workspace_permissions=principal.permissions,
                            required_permission=required, path_params=context, query_params={}, body=None)
                    else:
                        await authorizer.require_human_permission(user_id=principal.user_id, workspace_id=project.workspace_id,
                            project_id=project_id, permission=required, path_context=context)
                return await configuration_summary(session, project_id=project_id, environment=arguments['environment'],
                    inventory=_target_inventory, reader=_target_reader, authorize=authorize_target,
                    inspect=ConfigurationResolution(session, encryption_key=self.encryption_key).inspect)
            if action == "readiness":
                from shared.contracts.project_configuration import ConfigurationError
                if _target_reader is None:
                    raise ConfigurationError("CONFIG_STORE_UNAVAILABLE")
                closure = await _target_reader(session, project_id=project_id, **arguments)
                result, _ = await ConfigurationResolution(session, encryption_key=self.encryption_key).inspect(
                    project_id=project_id, environment=arguments["environment"], dependencies=closure["dependencies"])
                result["unresolved"] = closure["unresolved"]
                if result["unresolved"]:
                    result["state"] = "unknown"
                result.update({"target_kind": arguments["target_kind"], "target_id": str(arguments["target_id"]),
                               "selection": closure["selection"]})
                return result
            if action not in {"list_keys", "usage", "list_use_policies", "legacy_bindings"}:
                arguments["actor"] = actor
            store = LegacyConfigurationStore(session, encryption_key=self.encryption_key)
            result = await getattr(store, action)(project_id=project_id, **arguments)
            if action == "convert":
                result["routes"] = {env: result["routes"][env] for env in arguments["environments"]}
            if action == "list_keys":
                # A condition on Draft does not authorize a cross-environment
                # comparison. Clients request each authorized Environment.
                environment = result["environment"]
                for item in result["items"]:
                    item["values"] = {environment: item["values"][environment]}
                result["permissions"] = {}
                for operation in ("declare", "value:write", "value:clear", "use-policy:write", "migrate"):
                    try:
                        required = "project:environment:" + operation
                        context = {"project_id": project_id, "environment": environment}
                        if isinstance(principal, ControlPlanePrincipal):
                            await authorizer.authorize_control_key(api_key_id=principal.api_key_id,
                                workspace_id=principal.workspace_id, workspace_permissions=principal.permissions,
                                required_permission=required, path_params=context, query_params={}, body=None)
                        else:
                            await authorizer.require_human_permission(user_id=principal.user_id, workspace_id=project.workspace_id,
                                project_id=project_id, permission=required, path_context=context)
                        result["permissions"][operation] = True
                    except (AuthorizationError, NotFoundError):
                        result["permissions"][operation] = False
            return result
