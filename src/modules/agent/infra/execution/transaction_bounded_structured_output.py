from uuid import UUID

from langchain_core.messages import SystemMessage

from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.interfaces.outbox import OutboxEventWriter
from modules.agent.application.runtime_tool_inventory import RUNTIME_TOOL_INVENTORY_NAME
from modules.agent.application.tool_converter import agent_tools_to_openai_definitions_and_mapping
from modules.agent.application.tool_release_snapshots import tool_with_permission_overrides
from modules.agent.infra.database.runtime_repositories import AgentRuntimeRepositories
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
    """Structured Agent runtime with external I/O outside DB transactions."""

    async def _prepare(self, input_dto):
        token = _rag_history_context.set([])
        try:
            # Skip StructuredOutputAskAgentUseCase._prepare because its legacy MCP
            # refresh couples network discovery to a database transaction. The
            # persistence/RAG phases below are already transaction-bounded.
            prepared = await super(StructuredOutputAskAgentUseCase, self)._prepare(
                input_dto
            )
            prepared = await self._apply_runtime_tool_selection(prepared)
            agent = prepared[0]
            context = current_execution.get()
            tool_metadata = context.tool_metadata if context else None
            tool_source = tool_metadata.get("source") if tool_metadata else None

            if tool_source == "release_snapshot":
                updated = list(prepared)
                tool_name_to_id = updated[8]
            else:
                async def load_tools(
                    repositories: AgentRuntimeRepositories,
                    _outbox: OutboxEventWriter,
                ):
                    if tool_source == "draft_live" and tool_metadata:
                        tools = []
                        for raw_tool_id in tool_metadata.get("tool_ids", []):
                            tool = await repositories.tools.get_by_id(
                                UUID(str(raw_tool_id))
                            )
                            if tool is not None:
                                tools.append(tool)
                    else:
                        tools = await repositories.tools.list_by_agent(
                            agent.id,
                            status="active",
                        )

                    permission_overrides = (
                        tool_metadata.get("permission_overrides")
                        if tool_metadata
                        else None
                    )
                    if isinstance(permission_overrides, dict):
                        tools = [
                            tool_with_permission_overrides(
                                tool,
                                permission_overrides.get(str(tool.id)),
                            )
                            for tool in tools
                        ]
                    return agent_tools_to_openai_definitions_and_mapping(tools)

                try:
                    agent_tools, tool_name_to_id = await self._transactions.run(
                        load_tools
                    )
                except Exception:
                    updated = list(prepared)
                    tool_name_to_id = updated[8]
                else:
                    updated = list(prepared)
                    updated[7] = agent_tools
                    updated[8] = tool_name_to_id
                    updated[9] = bool(agent_tools)

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
                messages.insert(
                    insert_at,
                    SystemMessage(content=_TOOL_GROUNDING_RUNTIME_RULES),
                )
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
