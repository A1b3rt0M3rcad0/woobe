from modules.agent.application.skill_bindings import (
    freeze_skill_bindings,
    frozen_enabled_skills,
)
from modules.agent.application.skill_runtime import SkillRuntime
from modules.agent.infra.execution.instrumented_execution_runner import (
    configure_skill_runtime,
)
from modules.agent.infra.execution.runtime_preparation import (
    configure_skill_binding_freezer,
)


configure_skill_runtime(frozen_enabled_skills, SkillRuntime)
configure_skill_binding_freezer(freeze_skill_bindings)
