from modules.agent.application.execution_snapshot import build_agent_execution_snapshot
from modules.agent.application.portable_export_tools import export_frozen_tool
from modules.agent.application.skill_bindings import frozen_enabled_skills
from modules.agent.domain.model_spec import ModelSpec, model_spec_hash
from shared.contracts.errors import ConflictError


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
    def tool(snapshot):
        return export_frozen_tool(snapshot)

    @staticmethod
    def validate_skills(runtime, project_id):
        return frozen_enabled_skills(runtime, project_id)
