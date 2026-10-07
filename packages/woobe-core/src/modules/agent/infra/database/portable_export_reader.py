"""Capture native executable definitions and dependency metadata before storage IO."""

from copy import deepcopy
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select, text

from modules.agent.domain.skills import skill_package_hash
from modules.agent.application.dtos.portable_credential_metadata import (
    PortableCredentialMetadata,
)
from modules.agent.infra.database.models import (
    AgentModel,
    AgentToolModel,
    ProviderCredentialModel,
    AgentReleaseModel,
    AgentPromptModel,
    AgentContractModel,
    DocumentModel,
    DocumentCollectionModel,
    KnowledgeVersionModel,
)
from modules.agent.infra.database.provider_model_repositories import ProviderModelModel
from modules.agent.infra.database.mappers import model_to_tool
from modules.agent.infra.database.skill_models import SkillModel, SkillVersionModel
from modules.agent.infra.database.vector_snapshot_models import (
    VectorSnapshotModel,
    VectorSnapshotDocumentModel,
)
from shared.contracts.errors import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from shared.security.principal import AuthenticatedPrincipal, ControlPlanePrincipal
from shared.security.tenancy import TenantAuthorizer


async def authorize_export_read(
    session, principal, project_id, permission, *, identifiers
):
    authorizer = TenantAuthorizer(session)
    paths = {"project_id": str(project_id), **identifiers}
    if isinstance(principal, ControlPlanePrincipal):
        await authorizer.require_active_control(principal)
        await authorizer.authorize_control_key(
            api_key_id=principal.api_key_id,
            workspace_id=principal.workspace_id,
            workspace_permissions=principal.permissions,
            required_permission=permission,
            path_params=paths,
            query_params={},
            body={},
        )
    elif isinstance(principal, AuthenticatedPrincipal):
        await authorizer.require_active_human(principal)
        workspace_id = await authorizer._project_workspace_id(project_id)
        await authorizer.require_human_permission(
            user_id=principal.user_id,
            workspace_id=workspace_id,
            project_id=project_id,
            permission=permission,
            path_context=paths,
        )
    else:
        raise AuthorizationError("Administrative authentication is required")


def _metadata(model, fields):
    return {field: deepcopy(getattr(model, field)) for field in fields}


class PortableAgentExportReader:
    def __init__(
        self, uow_factory, storage=None, *, compiler, max_document_bytes=25 << 20
    ):
        self._uow_factory, self._compiler = uow_factory, compiler
        self._storage, self._max_document_bytes = storage, max_document_bytes

    async def _credential_intent(self, session, *, project_id, principal, identifier):
        credential = await session.get(ProviderCredentialModel, UUID(str(identifier)))
        if credential is None or credential.project_id != project_id:
            raise ConflictError("Snapshot provider credential metadata is unavailable")
        await authorize_export_read(
            session,
            principal,
            project_id,
            "provider:read",
            identifiers={"provider_credential_id": str(credential.id)},
        )
        metadata = PortableCredentialMetadata.model_validate(
            {
                key: value
                for key, value in (credential.meta or {}).items()
                if key in {"provider_family", "compatibility", "base_url"}
            }
        ).model_dump(exclude_none=True)
        return {
            "provider": credential.provider,
            "metadata": metadata,
        }

    async def read_documents(self, *, project_id, principal, documents):
        if self._storage is None:
            raise ValidationError("Portable document storage is unavailable")
        captured = []
        async with self._uow_factory() as uow:
            session = uow.session
            for expected in documents:
                document = await session.get(DocumentModel, UUID(str(expected["id"])))
                if document is None or document.project_id != project_id:
                    raise NotFoundError("Portable document is unavailable")
                await authorize_export_read(
                    session,
                    principal,
                    project_id,
                    "knowledge:read",
                    identifiers={"document_id": str(document.id)},
                )
                if (
                    any(
                        getattr(document, field) != expected[field]
                        for field in ("storage_key", "sha256", "size_bytes")
                    )
                    or not 0 < document.size_bytes <= self._max_document_bytes
                ):
                    raise ConflictError("Captured document changed before storage read")
                captured.append(dict(expected))
        contents = []
        for document in captured:
            content = await self._storage.read_document_bounded(
                document["storage_key"], max_bytes=self._max_document_bytes
            )
            if (
                len(content) != document["size_bytes"]
                or sha256(content).hexdigest() != document["sha256"]
            ):
                raise ConflictError("Captured document failed its byte integrity check")
            contents.append(content)
        return contents

    async def capture(self, *, project_id, principal, sources):
        async with self._uow_factory() as uow:
            session = uow.session
            if session.bind.dialect.name == "postgresql":
                await session.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                )
            return [
                await self.capture_in_session(
                    session, project_id=project_id, principal=principal, **source
                )
                for source in sources
            ]

    async def _live_draft_definition(self, session, *, agent, project_id, principal):
        models = {}
        for prefix, credential_field, model_field in (
            ("", "provider_credential_id", "model"),
            ("fallback_", "fallback_credential_id", "fallback_model"),
        ):
            credential_id = getattr(agent, credential_field)
            if prefix and credential_id is None:
                continue
            candidates = (
                await session.scalars(
                    select(ProviderModelModel).where(
                        ProviderModelModel.project_id == project_id,
                        ProviderModelModel.provider_credential_id == credential_id,
                        ProviderModelModel.model == getattr(agent, model_field),
                        ProviderModelModel.status == "active",
                    )
                )
            ).all()
            candidates = [
                self._compiler.capture_model(
                    model, provider=getattr(agent, prefix + "provider")
                )
                for model in candidates
            ]
            declared = (agent.settings or {}).get(prefix + "model_spec")
            if declared:
                candidates = [model for model in candidates if model.spec == declared]
            if not candidates or len({model.spec_hash for model in candidates}) != 1:
                raise ConflictError("Draft has no unambiguous complete Provider Model")
            model = candidates[0]
            await authorize_export_read(
                session,
                principal,
                project_id,
                "provider:read",
                identifiers={"provider_model_id": str(model.id)},
            )
            models[prefix] = model
        tool_ids = (
            ((agent.settings or {}).get("runtime_config") or {}).get("tools") or {}
        ).get("tool_ids") or []
        tools = []
        for identifier in tool_ids:
            native = await session.get(AgentToolModel, UUID(str(identifier)))
            if native is None or native.project_id != project_id:
                raise ConflictError("Draft Tool is unavailable")
            await authorize_export_read(
                session,
                principal,
                project_id,
                "tool:read",
                identifiers={"tool_id": str(native.id)},
            )
            tools.append(model_to_tool(native))
        return self._compiler.freeze_draft(agent, models=models, tools=tools)

    async def capture_in_session(
        self,
        session,
        *,
        project_id,
        principal,
        agent_id,
        source=None,
        snapshot_id=None,
        expected_snapshot=None,
    ):
        if (source is None) == (snapshot_id is None):
            raise ValidationError("Export requires source or snapshot identity")
        await authorize_export_read(
            session,
            principal,
            project_id,
            "agent:read",
            identifiers={"agent_id": str(agent_id)},
        )
        agent = await session.get(AgentModel, agent_id)
        if agent is None or agent.project_id != project_id:
            raise NotFoundError("Agent is unavailable")
        if snapshot_id is not None:
            release = await session.get(AgentReleaseModel, snapshot_id)
        else:
            if source not in {"draft", "staging", "release", "production"}:
                raise ValidationError("Invalid export source")
            query = select(AgentReleaseModel).where(
                AgentReleaseModel.agent_id == agent_id,
                AgentReleaseModel.project_id == project_id,
            )
            query = (
                query.where(AgentReleaseModel.snapshot_kind == "release")
                if source == "release"
                else query.where(AgentReleaseModel.status == source)
            )
            release = await session.scalar(
                query.order_by(
                    AgentReleaseModel.created_at.desc(), AgentReleaseModel.id.desc()
                ).limit(1)
            )
        if release is None and source == "draft":
            definition = await self._live_draft_definition(
                session, agent=agent, project_id=project_id, principal=principal
            )
        else:
            if (
                release is None
                or release.project_id != project_id
                or release.agent_id != agent_id
            ):
                raise NotFoundError("Agent snapshot is unavailable")
            await authorize_export_read(
                session,
                principal,
                project_id,
                "agent:read",
                identifiers={"agent_id": str(agent_id), "release_id": str(release.id)},
            )
            definition = self._compiler.definition(release)
        if expected_snapshot is not None and any(
            definition.get(key) != value for key, value in expected_snapshot.items()
        ):
            raise ConflictError(
                "Agent snapshot differs from the frozen Network binding"
            )
        credentials = {}
        for field in ("provider_credential_id", "fallback_credential_id"):
            if identifier := definition.get(field):
                credentials[str(identifier)] = await self._credential_intent(
                    session,
                    project_id=project_id,
                    principal=principal,
                    identifier=identifier,
                )
        runtime = definition["runtime_config"]
        tools = []
        tool_config = runtime.get("tools") or {}
        snapshots = tool_config.get("snapshots") or []
        if {str(item.get("id")) for item in snapshots} != set(
            map(str, tool_config.get("tool_ids") or [])
        ):
            raise ConflictError("Snapshot has incomplete frozen Tool definitions")
        for snapshot in snapshots:
            tool = self._compiler.tool(snapshot)
            if UUID(str(snapshot["project_id"])) != project_id:
                raise ConflictError("Frozen Tool belongs to another Project")
            await authorize_export_read(
                session,
                principal,
                project_id,
                "tool:read",
                identifiers={"tool_id": tool["id"]},
            )
            tools.append(tool)
        # The verified native snapshots may contain encrypted OAuth runtime state.
        # Keep only author-safe projections outside this owner read boundary.
        if "tools" in runtime:
            runtime["tools"].pop("snapshots", None)
        self._compiler.validate_skills(runtime, project_id)
        skills = []
        frozen_skills = {
            item["skill_version_id"]: item
            for item in (runtime.get("skills") or {}).get("snapshots", [])
        }
        for binding in (runtime.get("skills") or {}).get("bindings", []):
            version = await session.get(
                SkillVersionModel, UUID(str(binding["skill_version_id"]))
            )
            skill = await session.get(SkillModel, UUID(str(binding["skill_id"])))
            if (
                version is None
                or skill is None
                or version.skill_id != skill.id
                or skill.project_id != project_id
                or skill_package_hash(version.package) != version.package_hash
                or frozen_skills.get(str(version.id), {}).get("package_hash")
                != version.package_hash
                or frozen_skills.get(str(version.id), {}).get("package")
                != version.package
            ):
                raise ConflictError("Frozen Skill package is unavailable")
            await authorize_export_read(
                session,
                principal,
                project_id,
                "skill:read",
                identifiers={"skill_id": str(skill.id)},
            )
            skills.append(
                {
                    "id": str(version.id),
                    "skill_id": str(skill.id),
                    "name": frozen_skills[str(version.id)].get(
                        "name", version.package.get("name", skill.name)
                    ),
                    "version": version.version,
                    "package": deepcopy(version.package),
                    "package_hash": version.package_hash,
                    "enabled": binding.get("enabled", True),
                }
            )
        artifacts = {}
        for field, model, fields in (
            (
                "prompt_version_id",
                AgentPromptModel,
                ("version", "name", "content", "content_hash"),
            ),
            (
                "contract_version_id",
                AgentContractModel,
                (
                    "version",
                    "name",
                    "input_schema",
                    "output_schema",
                    "validation_mode",
                    "repair_attempts",
                    "additional_instructions",
                    "schema_hash",
                ),
            ),
        ):
            if identifier := definition.get(field):
                artifact = await session.get(model, UUID(str(identifier)))
                if (
                    artifact is None
                    or artifact.project_id != project_id
                    or artifact.agent_id != agent_id
                ):
                    raise ConflictError("Snapshot lineage artifact is unavailable")
                artifacts[field] = _metadata(artifact, fields)
        knowledge = None
        if identifier := definition.get("knowledge_version_id"):
            version = await session.get(KnowledgeVersionModel, UUID(str(identifier)))
            if (
                version is None
                or version.project_id != project_id
                or version.agent_id != agent_id
            ):
                raise ConflictError("Snapshot KnowledgeVersion is unavailable")
            vector_id = (version.snapshot_metadata or {}).get("vector_snapshot_id")
            vector = (
                await session.get(VectorSnapshotModel, UUID(str(vector_id)))
                if vector_id
                else None
            )
            if (
                vector is None
                or vector.project_id != project_id
                or vector.status != "READY"
                or not vector.snapshot_hash
            ):
                raise ConflictError("Snapshot Knowledge is not ready")
            await authorize_export_read(
                session,
                principal,
                project_id,
                "knowledge:read",
                identifiers={"vector_snapshot_id": str(vector.id)},
            )
            collection = await session.get(
                DocumentCollectionModel, vector.collection_id
            )
            if collection is None or collection.project_id != project_id:
                raise ConflictError("Snapshot collection is unavailable")
            documents = []
            rows = await session.execute(
                select(VectorSnapshotDocumentModel, DocumentModel)
                .join(
                    DocumentModel,
                    DocumentModel.id == VectorSnapshotDocumentModel.document_id,
                )
                .where(VectorSnapshotDocumentModel.vector_snapshot_id == vector.id)
                .order_by(VectorSnapshotDocumentModel.document_id)
            )
            for frozen, document in rows:
                if (
                    document.project_id != project_id
                    or document.collection_id != vector.collection_id
                    or document.sha256 != frozen.document_sha256
                    or not document.sha256
                ):
                    raise ConflictError(
                        "Snapshot document changed after vector capture"
                    )
                documents.append(
                    _metadata(
                        document,
                        (
                            "id",
                            "title",
                            "file_name",
                            "content_type",
                            "size_bytes",
                            "storage_key",
                            "sha256",
                        ),
                    )
                )
            if len(documents) != vector.document_count:
                raise ConflictError("Snapshot document closure is incomplete")
            model = await session.get(
                ProviderModelModel, vector.embedding_provider_model_id
            )
            if model is None or model.project_id != project_id:
                raise ConflictError("Embedding Model is unavailable")
            self._compiler.validate_model_authentication(model.spec, model.meta)
            credential_id = str(model.provider_credential_id)
            if credential_id not in credentials:
                credentials[credential_id] = await self._credential_intent(
                    session,
                    project_id=project_id,
                    principal=principal,
                    identifier=credential_id,
                )
            knowledge = {
                "collection": _metadata(collection, ("name", "description")),
                "documents": documents,
                "vector": _metadata(
                    vector,
                    (
                        "id",
                        "snapshot_hash",
                        "build_config",
                        "chunk_size",
                        "chunk_overlap",
                        "chunking_strategy",
                        "parser_config",
                        "embedding_provider",
                        "embedding_model",
                        "embedding_dimensions",
                    ),
                ),
                "embedding": _metadata(
                    model,
                    (
                        "model",
                        "model_type",
                        "meta",
                        "spec",
                        "spec_hash",
                        "provider_credential_id",
                    ),
                ),
            }
        return {
            "source": {
                "agent_id": str(agent_id),
                "snapshot_id": str(release.id) if release else None,
                "version": release.version if release else None,
                "kind": release.snapshot_kind if release else "draft",
            },
            "definition": definition,
            "tools": tools,
            "credentials": credentials,
            "skills": skills,
            "artifacts": artifacts,
            "knowledge": knowledge,
        }
