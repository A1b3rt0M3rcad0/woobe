from __future__ import annotations

from dataclasses import replace

from modules.agent.application.context_assembly import (
    ContextAssemblyResult,
    assemble_context,
)
from modules.agent.application.interfaces.context_assembler import (
    ContextAssembler,
    ContextAssemblyOutput,
    ContextAssemblyRequest,
)
from modules.agent.application.interfaces.context_manager import ContextManager
from modules.agent.infra.context_management.manager_runtime.context import (
    RuntimeContextManagerContext,
)
from modules.agent.infra.context_management.manager_runtime.skills import (
    materialize_active_skills,
)


class ContextManagerRunner(ContextAssembler):
    """Adapt one programmable Context Manager to the outer ContextAssembler boundary."""

    __slots__ = ("_manager",)

    def __init__(self, manager: ContextManager) -> None:
        self._manager = manager

    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        ctx = RuntimeContextManagerContext(request)
        outcome = self._manager.assemble(ctx)

        messages = list(request.messages)
        policy = outcome.policy.model_copy(deep=True)
        active_skill_versions: tuple[str, ...] = ()

        if outcome.materialize_skills:
            messages, active_skill_versions = materialize_active_skills(
                request=request,
                messages=messages,
                policy=policy,
            )

        assembled = assemble_context(
            messages=messages,
            model_invocation_id=request.model_invocation_id,
            agent_run_id=request.agent_run_id,
            project_id=request.project_id,
            provider=request.provider,
            model=request.model,
            runtime_context=request.runtime_context,
            policy=policy,
        )

        if not active_skill_versions:
            return assembled

        manifest = dict(assembled.snapshot.manifest)
        manifest["skills"] = {
            "retention": "run",
            "instruction_compaction": "protected",
            "installed_catalog": True,
            "active_versions": list(active_skill_versions),
        }
        return ContextAssemblyResult(
            messages=assembled.messages,
            snapshot=replace(assembled.snapshot, manifest=manifest),
        )
