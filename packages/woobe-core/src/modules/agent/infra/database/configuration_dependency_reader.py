"""Agent-owned batched interpretation of frozen Network constituent snapshots."""
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import select, func, cast
from sqlalchemy.dialects.postgresql import JSONPATH

from modules.agent.infra.adapters.configuration_bindings import provider_dependencies
from modules.agent.infra.database.models import AgentReleaseModel, ProviderCredentialModel, AgentToolModel, KnowledgeVersionModel
from modules.agent.domain.tool_configuration import tool_dependencies
from shared.contracts.project_configuration import ConfigurationError


async def collect_configuration_dependencies(session, *, project_id, bindings, include_notices=False, snapshot_builder):
    snapshots, missing = [], {}
    for node_id, binding in bindings.items():
        if node_id == "asac_run_identity":
            continue
        if not isinstance(binding, dict):
            raise ConfigurationError("CONFIG_BINDING_INVALID")
        snapshot = binding.get("snapshot_override")
        # Runtime gives the immutable release precedence. Networks also carry
        # a small compatibility override (provider/model/pinned_release_id); it
        # is not the executable closure and must not hide its dependencies.
        release_id = binding.get("release_id")
        if isinstance(snapshot, dict) and not release_id:
            if snapshot.get("pinned_release_id"):
                raise ConfigurationError("CONFIG_BINDING_INVALID")
            snapshots.append((node_id, snapshot))
        else:
            try:
                missing[node_id] = UUID(str(release_id or binding.get("draft_release_id")))
                if isinstance(snapshot, dict) and snapshot.get("pinned_release_id") not in (None, str(missing[node_id])):
                    raise ConfigurationError("CONFIG_BINDING_INVALID")
            except ValueError:
                raise ConfigurationError("CONFIG_BINDING_INVALID") from None
    if missing:
        rows = (await session.scalars(select(AgentReleaseModel).where(
            AgentReleaseModel.project_id == project_id, AgentReleaseModel.id.in_(set(missing.values()))))).all()
        releases = {r.id: r for r in rows}
        for node_id, identifier in missing.items():
            if identifier not in releases or (bindings[node_id].get("agent_id")
                    and str(releases[identifier].agent_id) != str(bindings[node_id]["agent_id"])):
                raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
            snapshots.append((node_id, snapshot_builder(releases[identifier])))
    identifiers = set()
    for _, snapshot in snapshots:
        for field in ("provider_credential_id", "fallback_credential_id"):
            if snapshot.get(field):
                try:
                    identifiers.add(UUID(str(snapshot[field])))
                except ValueError:
                    raise ConfigurationError("CONFIG_BINDING_INVALID") from None
    knowledge_ids = {UUID(str(snapshot["knowledge_version_id"])) for _, snapshot in snapshots if snapshot.get("knowledge_version_id")}
    knowledge_bindings = {}
    if knowledge_ids:
        from modules.agent.infra.database.vector_snapshot_models import VectorSnapshotModel
        from modules.agent.infra.database.provider_model_repositories import ProviderModelModel
        knowledge_rows = (await session.execute(select(KnowledgeVersionModel.id,
            KnowledgeVersionModel.snapshot_metadata["vector_snapshot_id"].astext.label("vector_id"))
            .where(KnowledgeVersionModel.project_id == project_id, KnowledgeVersionModel.id.in_(knowledge_ids)))).all()
        vector_ids = {UUID(row.vector_id) for row in knowledge_rows if row.vector_id}
        vector_rows = (await session.execute(select(VectorSnapshotModel.id, VectorSnapshotModel.status,
            VectorSnapshotModel.snapshot_hash, VectorSnapshotModel.embedding_provider,
            ProviderModelModel.provider_credential_id, ProviderModelModel.meta, ProviderModelModel.status.label("model_status"))
            .join(ProviderModelModel, ProviderModelModel.id == VectorSnapshotModel.embedding_provider_model_id)
            .where(VectorSnapshotModel.project_id == project_id, ProviderModelModel.project_id == project_id,
                VectorSnapshotModel.id.in_(vector_ids)))).all() if vector_ids else []
        vectors = {str(row.id): row for row in vector_rows}
        for row in knowledge_rows:
            vector = vectors.get(row.vector_id)
            if vector is None or vector.status != "READY" or not vector.snapshot_hash or vector.model_status != "active":
                continue
            knowledge_bindings[str(row.id)] = vector
            identifiers.add(vector.provider_credential_id)
    # No provider material is selected during acceptance/readiness.
    rows = (await session.execute(select(ProviderCredentialModel.id, ProviderCredentialModel.project_id,
        ProviderCredentialModel.provider, ProviderCredentialModel.authentication,
        ProviderCredentialModel.binding_revision, ProviderCredentialModel.meta,
        ProviderCredentialModel.status).where(ProviderCredentialModel.project_id == project_id,
        ProviderCredentialModel.id.in_(identifiers)))).all() if identifiers else []
    credentials = {r.id: SimpleNamespace(id=r.id, project_id=r.project_id, provider=r.provider,
        authentication=r.authentication, binding_revision=r.binding_revision, metadata=r.meta, status=r.status) for r in rows}
    result, notices = [], []
    # Select only public Tool connection metadata, never OAuth/secret material.
    live_agents, tool_ids = set(), set()
    for node_id, snapshot in snapshots:
        config = (snapshot.get("runtime_config") or {}).get("tools") or {}
        ids = config.get("tool_ids")
        frozen = {str(item.get("id")): item for item in config.get("snapshots", []) if isinstance(item, dict)}
        for identifier in ids or []:
            if str(identifier) not in frozen:
                tool_ids.add(UUID(str(identifier)))
        if not ids and not frozen:
            identifier = (bindings.get(node_id) or {}).get("agent_id")
            if identifier:
                live_agents.add(UUID(str(identifier)))
    tool_rows = []
    if live_agents or tool_ids:
        from sqlalchemy import or_
        tool_rows = (await session.execute(select(AgentToolModel.id, AgentToolModel.agent_id, AgentToolModel.status,
            AgentToolModel.config["authentication"].label("authentication"),
            AgentToolModel.config["url"].astext.label("url"),
            AgentToolModel.config["base_url"].astext.label("base_url"),
            AgentToolModel.config["server"]["url"].astext.label("server_url"),
            func.jsonb_path_query_array(AgentToolModel.config, cast('$.headers[*] ? (@.value starts with "{{secret:")', JSONPATH)).label("secret_headers"),
            func.jsonb_path_query_array(AgentToolModel.config, cast('$.server_headers[*] ? (@.value starts with "{{secret:")', JSONPATH)).label("secret_server_headers"),
            func.jsonb_path_query_array(AgentToolModel.config, cast('$.server.headers[*] ? (@.value starts with "{{secret:")', JSONPATH)).label("secret_nested_headers")
        ).where(AgentToolModel.project_id == project_id, or_(AgentToolModel.id.in_(tool_ids),
            AgentToolModel.agent_id.in_(live_agents))))).all()
    available_tools = {str(row.id): SimpleNamespace(id=row.id, project_id=project_id, agent_id=row.agent_id,
        status=row.status, config={"authentication": row.authentication, "url": row.url,
        "base_url": row.base_url, "headers": row.secret_headers, "server_headers": row.secret_server_headers,
        "server": {"url": row.server_url, "headers": row.secret_nested_headers}}) for row in tool_rows}

    from modules.agent.infra.database.configuration_secret_projection import project_secret_headers
    projected = await project_secret_headers(session, project_id=project_id, tools=list(available_tools.values()))
    available_tools = {str(tool.id): tool for tool in projected}
    frozen_inputs, frozen_keys = [], []
    for node_id, snapshot in snapshots:
        for raw in ((snapshot.get("runtime_config") or {}).get("tools") or {}).get("snapshots", []):
            if isinstance(raw, dict) and raw.get("id"):
                frozen_inputs.append(SimpleNamespace(id=UUID(str(raw["id"])), project_id=project_id,
                    config=raw.get("config") or {}, status=raw.get("status", "active")))
                frozen_keys.append((node_id, str(raw["id"])))
    projected = await project_secret_headers(session, project_id=project_id, tools=frozen_inputs)
    frozen_tools = dict(zip(frozen_keys, projected, strict=True))

    for node_id, snapshot in snapshots:
        for field in ("provider_credential_id", "fallback_credential_id"):
            if not snapshot.get(field):
                continue
            credential = credentials.get(UUID(str(snapshot[field])))
            if credential is None or credential.status != "active":
                raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
            if credential.authentication is None:
                notices.append({"code": "LEGACY_CONFIGURATION_REVIEW_REQUIRED", "consumer_kind": "provider_credential",
                    "consumer_id": str(credential.id), "field_path": "/authentication/fields/api_key"})
            result.extend(provider_dependencies(credential, base_url=snapshot.get("base_url") if field == "provider_credential_id" else None,
                impact=(("network_node", node_id),)))
        runtime = snapshot.get("runtime_config") or {}
        tools = runtime.get("tools") or {}
        frozen = {str(item.get("id")): item for item in tools.get("snapshots", []) if isinstance(item, dict)}
        selected = tools.get("tool_ids") or list(frozen)
        if not selected:
            agent_id = (bindings.get(node_id) or {}).get("agent_id")
            selected = [identifier for identifier, item in available_tools.items()
                if str(item.agent_id) == str(agent_id) and item.status == "active"]
        for identifier in selected:
            if str(identifier) in frozen:
                tool = frozen_tools[(node_id, str(identifier))]
            else:
                tool = available_tools.get(str(identifier))
            if tool is None or tool.status != "active":
                raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
            if tool.config.get("authentication") is None:
                notices.append({"code": "LEGACY_CONFIGURATION_REVIEW_REQUIRED", "consumer_kind": "tool", "consumer_id": str(tool.id)})
            else:
                result.extend(tool_dependencies(tool, impact=(("agent", node_id),)))
        if snapshot.get("knowledge_version_id"):
            knowledge = knowledge_bindings.get(str(snapshot["knowledge_version_id"]))
            if knowledge is None:
                notices.append({"code": "CONFIG_CLOSURE_REVIEW_REQUIRED", "consumer_kind": "knowledge", "consumer_id": str(snapshot["knowledge_version_id"])})
            else:
                credential = credentials.get(knowledge.provider_credential_id)
                if credential is None or credential.status != "active":
                    raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
                if credential.authentication is None:
                    notices.append({"code": "LEGACY_CONFIGURATION_REVIEW_REQUIRED", "consumer_kind": "provider_credential", "consumer_id": str(credential.id)})
                from modules.agent.infra.execution.rag.embedding_capability import embedding_base_url
                result.extend(provider_dependencies(credential,
                    base_url=embedding_base_url(knowledge, SimpleNamespace(metadata=knowledge.meta), credential),
                    impact=(("knowledge", str(snapshot["knowledge_version_id"])),)))
        elif snapshot.get("collection_ids"):
            notices.append({"code": "CONFIG_CLOSURE_REVIEW_REQUIRED", "consumer_kind": "knowledge", "consumer_id": node_id})
    return {"dependencies": result, "unresolved": notices} if include_notices else result


async def read_configuration_target(session, *, project_id, target_kind, target_id, environment, version_id=None, snapshot_builder, target_resolver):
    """Use the same environment selector as runtime, never a current-Agent shortcut."""
    selection = {"environment": environment, "version_id": None, "source": "provider"}
    if target_kind == "provider_credential":
        if version_id is not None:
            raise ConfigurationError("CONFIG_BINDING_INVALID")
        bindings = {str(target_id): {"snapshot_override": {"provider_credential_id": str(target_id)}}}
    elif target_kind == "tool":
        if version_id is not None:
            raise ConfigurationError("CONFIG_BINDING_INVALID")
        bindings = {str(target_id): {"snapshot_override": {"runtime_config": {"tools": {"tool_ids": [str(target_id)]}}}}}
        selection["source"] = "tool"
    elif target_kind == "agent":
        candidate = await session.scalar(select(AgentReleaseModel.id).where(
            AgentReleaseModel.id == version_id, AgentReleaseModel.project_id == project_id,
            AgentReleaseModel.agent_id == target_id, AgentReleaseModel.snapshot_kind == "candidate")) if version_id else None
        if candidate is not None:
            # Metadata inspection is authorized independently of Candidate Run
            # admission. It neither opens a Session nor grants runtime execution.
            if environment != "staging":
                raise ConfigurationError("CONFIG_BINDING_INVALID")
            bindings = {str(target_id): {"release_id": str(candidate), "agent_id": str(target_id)}}
            selection = {"environment": environment, "version_id": str(candidate), "source": "candidate"}
        else:
            resolver = target_resolver(session)
            resolved = await resolver.resolve(project_id=project_id, agent_id=target_id, environment=environment,
                release_id=version_id, allow_legacy_draft=True)
            bindings = {str(target_id): {"snapshot_override": resolved.snapshot, "agent_id": str(target_id)}}
            selection = {"environment": environment, "version_id": str(resolved.release_id) if resolved.release_id else None, "source": resolved.source}
    else:
        raise ConfigurationError("CONFIG_BINDING_INVALID")
    result = await collect_configuration_dependencies(session, project_id=project_id, bindings=bindings, include_notices=True, snapshot_builder=snapshot_builder)
    result["selection"] = selection
    return result
