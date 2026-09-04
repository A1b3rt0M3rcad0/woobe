from __future__ import annotations

from modules.agent.application.context_assembly import assemble_context
from modules.agent.application.interfaces.context_assembler import (
    ContextAssembler,
    ContextAssemblyOutput,
    ContextAssemblyRequest,
)


class DefaultContextAssembler(ContextAssembler):
    """Current deterministic Context Assembly strategy used by Woobe.

    The implementation is stateless by design so a composed runtime may safely reuse
    the same assembler instance across concurrent Agent Runs and Model Invocations.
    """

    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        return assemble_context(
            messages=request.messages,
            model_invocation_id=request.model_invocation_id,
            agent_run_id=request.agent_run_id,
            project_id=request.project_id,
            provider=request.provider,
            model=request.model,
            runtime_context=request.runtime_context,
            policy=request.policy,
        )
