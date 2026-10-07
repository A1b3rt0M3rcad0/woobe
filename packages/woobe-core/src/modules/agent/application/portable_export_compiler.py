from copy import deepcopy
from types import SimpleNamespace
from modules.agent.application.tool_release_snapshots import tool_to_release_snapshot
from modules.agent.application.execution_snapshot import build_agent_execution_snapshot
from modules.agent.application.portable_export_tools import export_frozen_tool
from modules.agent.application.skill_bindings import frozen_enabled_skills
from modules.agent.domain.model_spec import ModelSpec, model_spec_hash
from shared.contracts.errors import ConflictError
from modules.agent.application.model_spec_compatibility import LegacyModelSpecResolver


class PortableAgentExportCompiler:
    @staticmethod
    def definition(release):
        definition = build_agent_execution_snapshot(release)
        for prefix in ("", "fallback_"):
            specification = definition.get(prefix + "model_spec_snapshot")
            expected = definition.get(prefix + "model_spec_hash")
            if (
                specification is not None
                and model_spec_hash(ModelSpec.from_dict(specification)) != expected
            ):
                raise ConflictError("Snapshot ModelSpec integrity check failed")
        return definition

    @staticmethod
    def capture_model(model, *, provider):
        specification = deepcopy(model.spec)
        if specification is None:
            legacy = SimpleNamespace(
                id=model.id,
                name=model.name,
                model=model.model,
                provider_credential_id=model.provider_credential_id,
                metadata=deepcopy(model.meta or {}),
            )
            specification = (
                LegacyModelSpecResolver()
                .resolve(legacy, provider=str(provider))
                .as_dict()
            )
        fingerprint = model_spec_hash(ModelSpec.from_dict(specification))
        if model.spec_hash is not None and model.spec_hash != fingerprint:
            raise ConflictError("Draft Provider Model specification integrity failed")
        return SimpleNamespace(id=model.id, spec=specification, spec_hash=fingerprint)

    @staticmethod
    def freeze_draft(agent, *, models, tools):
        # A live Draft is captured without creating a release or changing owner state.
        settings = deepcopy(agent.settings or {})
        runtime = deepcopy(settings.get("runtime_config") or {})
        if "tools" in runtime:
            runtime["tools"]["snapshots"] = [
                tool_to_release_snapshot(tool) for tool in tools
            ]
        source = SimpleNamespace(
            **{
                field: deepcopy(getattr(agent, field, None))
                for field in (
                    "id",
                    "project_id",
                    "name",
                    "description",
                    "behavior_spec",
                    "system_prompt",
                    "provider",
                    "model",
                    "provider_credential_id",
                    "fallback_provider",
                    "fallback_model",
                    "fallback_credential_id",
                    "temperature",
                    "max_output_tokens",
                    "session_mode",
                    "status",
                )
            },
            settings=settings,
            runtime_config=runtime,
        )
        for prefix, model in models.items():
            setattr(source, prefix + "provider_model_id", model.id)
            setattr(source, prefix + "model_spec_snapshot", deepcopy(model.spec))
            setattr(source, prefix + "model_spec_hash", model.spec_hash)
        return PortableAgentExportCompiler.definition(source)

    @staticmethod
    def tool(snapshot):
        return export_frozen_tool(snapshot)

    @staticmethod
    def validate_skills(runtime, project_id):
        return frozen_enabled_skills(runtime, project_id)
