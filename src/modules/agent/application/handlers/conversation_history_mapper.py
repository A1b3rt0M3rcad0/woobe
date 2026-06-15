from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from modules.agent.domain.entities import Message
from modules.agent.domain.errors import ConversationHistoryLoadError

logger = logging.getLogger(__name__)


def messages_to_langchain(messages: list[Message]) -> list:
    history: list = []
    for m in messages:
        try:
            role = m.role.value if hasattr(m.role, "value") else m.role
        except Exception:
            logger.warning("Skipping message with unreadable role (id=%s)", m.id)
            continue

        if role == "user":
            history.append(HumanMessage(content=m.content))
        elif role == "assistant":
            raw_tool_calls = (m.data or {}).get("tool_calls") or []
            tool_calls: list[dict[str, Any]] | None = None
            if raw_tool_calls:
                tool_calls = [
                    {"id": tc["tool_call_id"], "name": tc["tool_name"], "args": tc.get("input", {})}
                    for tc in raw_tool_calls if tc.get("tool_call_id")
                ]
            if tool_calls:
                history.append(AIMessage(content=m.content, tool_calls=tool_calls))
            else:
                history.append(AIMessage(content=m.content))

            if tool_calls:
                for tc in raw_tool_calls:
                    if tc.get("tool_call_id") and tc.get("output") is not None:
                        history.append(ToolMessage(
                            content=json.dumps(tc["output"]),
                            tool_call_id=tc["tool_call_id"],
                        ))
        elif role in ("system", "tool_call", "tool_result"):
            logger.warning(
                "Unsupported role '%s' in message history (id=%s, session_id=%s) — skipping",
                role, m.id, m.session_id,
            )
        else:
            logger.warning(
                "Unknown role '%s' in message history (id=%s, session_id=%s) — skipping",
                role, m.id, m.session_id,
            )
    return history


async def load_and_convert_history(
    message_repo,
    session_id,
    session_id_for_error,
    limit: int = 100,
) -> list:
    try:
        raw_messages = await message_repo.list_recent_by_session(session_id, limit=limit)
        while raw_messages:
            role = raw_messages[0].role.value if hasattr(raw_messages[0].role, "value") else raw_messages[0].role
            if role in ("tool_result", "tool_call"):
                raw_messages.pop(0)
            else:
                break
        truncated = len(raw_messages) < limit if limit else False
        logger.info(
            "Loaded %d messages for session %s (truncated=%s)",
            len(raw_messages), session_id, truncated,
        )
        return messages_to_langchain(raw_messages)
    except ConversationHistoryLoadError:
        raise
    except Exception as exc:
        logger.error(
            "Failed to load history for session %s: %s",
            session_id, exc,
        )
        raise ConversationHistoryLoadError(
            session_id=session_id_for_error,
            message=str(exc),
        ) from exc
