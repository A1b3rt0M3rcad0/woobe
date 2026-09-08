from modules.agent.application.execution_snapshot import (
    AgentExecutionSnapshotResolver,
    apply_agent_execution_snapshot,
)
from modules.agent.application.skill_bindings import (
    freeze_skill_bindings,
    frozen_enabled_skills,
)
from modules.agent.application.skill_runtime import SkillRuntime
from modules.agent.infra.execution.canonical_execution_snapshot_runtime_resolver import (
    configure_execution_snapshot_runtime,
)
from modules.agent.infra.execution.instrumented_execution_runner import (
    configure_skill_runtime,
)
from modules.agent.infra.execution.runtime_preparation import (
    configure_skill_binding_freezer,
)


configure_skill_runtime(frozen_enabled_skills, SkillRuntime)
configure_skill_binding_freezer(freeze_skill_bindings)
configure_execution_snapshot_runtime(
    AgentExecutionSnapshotResolver,
    apply_agent_execution_snapshot,
)
