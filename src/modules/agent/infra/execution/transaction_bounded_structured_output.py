from langchain_core.messages import SystemMessage

from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.runtime_tool_inventory import RUNTIME_TOOL_INVENTORY_NAME
from modules.agent.infra.execution.explicit_runtime_persistence import (
    ExplicitRuntimePersistenceMixin,
)
from modules.agent.infra.execution.structured_output_ask_use_case import (
    StructuredOutputAskAgentUseCase,
    _RUNTIME_TOOL_INVENTORY_RUNTIME_RULES,
    _TOOL_GROUNDING_RUNTIME_RULES,
)
from modules.agent.infra.execution.transaction_bounded_rag import (
    TransactionBoundedVectorSnapshotRAGMixin,
    _rag_history_context,
)


class TransactionBoundedStructuredOutputRuntime(
    TransactionBoundedVectorSnapshotRAGMixin,
    StructuredOutputAskAgentUseCase,
):
    """Structured runtime with all mutable bindings prepared before execution."""

    async def _prepare(self, input_dto):
        token = _rag_history_context.set([])
        try:
            # Acceptance already resolved Tools and RAG bindings. Avoid the legacy
            # MCP refresh path because it performs external discovery inside a DB TX.
            prepared = await super(StructuredOutputAskAgentUseCase, self)._prepare(
                input_dto
            )
            prepared = await self._apply_runtime_tool_selection(prepared)
            updated = list(prepared)
            tool_name_to_id = dict(updated[8])
            context = current_execution.get()

            if context and context.internal_tool_definitions:
                definitions = list(updated[7])
                mapping = dict(updated[8])
                internal_mapping = context.internal_tool_name_to_id or {}
                collisions = set(mapping).intersection(internal_mapping)
                if collisions:
                    raise ValueError(
                        "Network delegation tool name collides with an Agent Tool: "
                        + ", ".join(sorted(collisions))
                    )
                definitions.extend(context.internal_tool_definitions)
                mapping.update(internal_mapping)
                updated[7] = definitions
                updated[8] = mapping
                updated[9] = bool(definitions)
                tool_name_to_id = mapping

            if updated[9]:
                messages = list(updated[11])
                insert_at = len(messages) - 1 if messages else 0
                messages.insert(insert_at, SystemMessage(content=_TOOL_GROUNDING_RUNTIME_RULES))
                updated[11] = messages

            if RUNTIME_TOOL_INVENTORY_NAME in tool_name_to_id:
                messages = list(updated[11])
                insert_at = len(messages) - 1 if messages else 0
                messages.insert(
                    insert_at,
                    SystemMessage(content=_RUNTIME_TOOL_INVENTORY_RUNTIME_RULES),
                )
                updated[11] = messages
            return tuple(updated)
        finally:
            _rag_history_context.reset(token)

    async def _fail(self, trace_id, agent, session, error, input_dto) -> None:
        context = current_execution.get()
        if context and context.execution and context.execution.llm_calls:
            # StructuredOutput owns the rich instrumented finalizer. It now writes
            # telemetry + AgentRun terminal state in one persistence transaction.
            return await StructuredOutputAskAgentUseCase._fail(
                self,
                trace_id,
                agent,
                session,
                error,
                input_dto,
            )
        return await ExplicitRuntimePersistenceMixin._fail(
            self,
            trace_id,
            agent,
            session,
            error,
            input_dto,
        )
