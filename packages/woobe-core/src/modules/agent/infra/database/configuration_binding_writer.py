"""Owner-controlled metadata projection and CAS reference replacement."""
import hashlib
import json
from sqlalchemy import select
from modules.agent.infra.database.models import ProviderCredentialModel, AgentToolModel
from modules.agent.infra.database.repositories import SQLAlchemyProviderCredentialRepository, SQLAlchemyAgentToolRepository
from modules.agent.domain.tool_configuration import validate_tool_authentication
from shared.contracts.project_configuration import ConfigurationError, compile_authentication


def revision(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


async def configuration_binding(session, *, project_id, target_kind, target_id, authentication=None, expected_revision=None):
    writing = authentication is not None
    if target_kind == "provider_credential":
        if writing:
            repo = SQLAlchemyProviderCredentialRepository(session)
            credential = await repo.lock_by_id(target_id)
            if credential is None or credential.project_id != project_id:
                raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
            if str(credential.binding_revision) != expected_revision:
                raise ConfigurationError("CONFIG_REVISION_CONFLICT")
            if credential.authentication is None and credential.encrypted_secret:
                raise ConfigurationError("LEGACY_ENVIRONMENT_REQUIRED")
            compiled = compile_authentication(authentication)
            if compiled["type"] != "api_key":
                raise ConfigurationError("CONFIG_BINDING_INVALID")
            credential.authentication, credential.encrypted_secret = compiled, ""
            credential = await repo.update(credential)
            await session.flush()
            return {"target_kind": target_kind, "target_id": str(target_id), "revision": str(credential.binding_revision), "authentication": compiled}
        row = (await session.execute(select(ProviderCredentialModel.authentication, ProviderCredentialModel.binding_revision)
            .where(ProviderCredentialModel.id == target_id, ProviderCredentialModel.project_id == project_id))).one_or_none()
        if row is None:
            raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
        return {"target_kind": target_kind, "target_id": str(target_id), "revision": str(row.binding_revision), "authentication": row.authentication}
    if target_kind != "tool":
        raise ConfigurationError("CONFIG_BINDING_INVALID")
    if writing:
        repo = SQLAlchemyAgentToolRepository(session)
        tool = await repo.lock_by_id(target_id)
        if tool.project_id != project_id:
            raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
        public_config = {"authentication": tool.config.get("authentication"), "url": tool.config.get("url"), "base_url": tool.config.get("base_url"), "server_url": (tool.config.get("server") or {}).get("url")}
        if revision(public_config) != expected_revision:
            raise ConfigurationError("CONFIG_REVISION_CONFLICT")
        compiled = compile_authentication(authentication, allow_none=True)
        tool.config = {**tool.config, "authentication": compiled}
        validate_tool_authentication(tool.config)
        await repo.update(tool)
        await session.flush()
        public_config["authentication"] = compiled
    else:
        row = (await session.execute(select(AgentToolModel.config["authentication"].label("authentication"),
            AgentToolModel.config["url"].astext.label("url"), AgentToolModel.config["base_url"].astext.label("base_url"),
            AgentToolModel.config["server"]["url"].astext.label("server_url")).where(
            AgentToolModel.project_id == project_id, AgentToolModel.id == target_id))).one_or_none()
        if row is None:
            raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
        public_config = dict(row._mapping)
    return {"target_kind": target_kind, "target_id": str(target_id), "revision": revision(public_config), "authentication": public_config["authentication"]}
