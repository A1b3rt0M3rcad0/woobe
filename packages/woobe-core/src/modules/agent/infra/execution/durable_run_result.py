"""Resolve the final answer without copying message content into outbox summaries."""
from modules.agent.domain.enums import MessageRole
from modules.agent.domain.errors import MessageNotFoundError
from shared.contracts.errors import ConflictError


async def durable_run_result(repositories, run):
    result = dict(run.result) if isinstance(run.result, dict) else {}
    if isinstance(result.get("answer"), str) or run.output_message_id is None:
        return result or None
    try:
        message = await repositories.messages.get_by_id(run.output_message_id)
    except MessageNotFoundError:
        return result or None
    if message is None:
        return result or None
    if (message.id != run.output_message_id or message.project_id != run.project_id
            or message.agent_id != run.agent_id or message.session_id != run.session_id
            or message.role != MessageRole.ASSISTANT):
        raise ConflictError("Agent Run output message identity differs")
    # Resolve only the immutable exact output ID, never the Session's latest turn.
    if isinstance(message.content, str):
        result["answer"] = message.content
    return result or None
